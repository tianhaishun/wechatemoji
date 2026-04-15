"""微信 PC 版密钥提取 & 数据库解密模块

基于 wechat-decrypt (github.com/ylytdeng/wechat-decrypt) 方案：
- WCDB 在进程内存中缓存密钥，格式为 x'<64hex_enc_key><32hex_salt>'
- 用正则 x'([0-9a-fA-F]{64,192})' 扫描全进程内存
- 将 salt 与 db 文件 salt 匹配，HMAC 验证
- 使用 enc_key 直接解密（已是 PBKDF2 派生后的 raw key）

支持：
- 微信 4.x (Weixin.exe / Weixin.dll)
- 微信 3.x (WeChat.exe / WeChatWin.dll)
"""

import ctypes
import ctypes.wintypes as wt
import hashlib
import hmac as hmac_mod
import os
import re
import struct
import subprocess
import sys
import time
from typing import Optional

from Crypto.Cipher import AES

import config

# ==================== 常量 ====================

kernel32 = ctypes.windll.kernel32
MEM_COMMIT = 0x1000
READABLE = {0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80}
PAGE_SZ = 4096
KEY_SZ = 32
SALT_SZ = 16
IV_SZ = 16
HMAC_SZ = 64
RESERVE_SZ = 80
SQLITE_HDR = b"SQLite format 3\x00"
WECHAT_PROCESS_NAMES = {"WeChat.exe", "Weixin.exe"}


class MBI(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_uint64),
        ("AllocationBase", ctypes.c_uint64),
        ("AllocationProtect", wt.DWORD),
        ("_pad1", wt.DWORD),
        ("RegionSize", ctypes.c_uint64),
        ("State", wt.DWORD),
        ("Protect", wt.DWORD),
        ("Type", wt.DWORD),
        ("_pad2", wt.DWORD),
    ]


# ==================== 进程查找 ====================

def find_wechat_pid() -> int:
    """查找微信主进程 PID（占内存最大的那个）"""
    for name in WECHAT_PROCESS_NAMES:
        r = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {name}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True,
        )
        best = (0, 0)
        for line in r.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.strip('"').split('","')
            if len(parts) >= 5:
                try:
                    pid = int(parts[1])
                    mem = int(parts[4].replace(",", "").replace(" K", "").strip() or "0")
                    if mem > best[1]:
                        best = (pid, mem)
                except (ValueError, IndexError):
                    continue
        if best[0]:
            return best[0]
    return 0


def read_mem(handle, addr, size):
    """安全读取进程内存"""
    buf = ctypes.create_string_buffer(size)
    n = ctypes.c_size_t(0)
    if kernel32.ReadProcessMemory(handle, ctypes.c_uint64(addr), buf, size, ctypes.byref(n)):
        return buf.raw[: n.value]
    return None


def enum_regions(handle):
    """枚举所有可读内存区域"""
    regions = []
    addr = 0
    mbi = MBI()
    while addr < 0x7FFFFFFFFFFF:
        if kernel32.VirtualQueryEx(handle, ctypes.c_uint64(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)) == 0:
            break
        if mbi.State == MEM_COMMIT and mbi.Protect in READABLE and 0 < mbi.RegionSize < 500 * 1024 * 1024:
            regions.append((mbi.BaseAddress, mbi.RegionSize))
        nxt = mbi.BaseAddress + mbi.RegionSize
        if nxt <= addr:
            break
        addr = nxt
    return regions


# ==================== 密钥验证 ====================

def verify_key_for_db(enc_key: bytes, db_page1: bytes) -> bool:
    """验证 enc_key 是否能解密该数据库的 page 1"""
    salt = db_page1[:SALT_SZ]
    mac_salt = bytes(b ^ 0x3A for b in salt)
    mac_key = hashlib.pbkdf2_hmac("sha512", enc_key, mac_salt, 2, dklen=KEY_SZ)

    hmac_data = db_page1[SALT_SZ : PAGE_SZ - RESERVE_SZ + IV_SZ]
    stored_hmac = db_page1[PAGE_SZ - HMAC_SZ : PAGE_SZ]
    h = hmac_mod.new(mac_key, hmac_data, hashlib.sha512)
    h.update(struct.pack("<I", 1))
    return h.digest() == stored_hmac


# ==================== 密钥提取 ====================

def extract_key_for_db(db_path: str, callback=None) -> Optional[str]:
    """从微信进程内存中提取指定数据库的解密密钥

    核心原理：WCDB 缓存密钥格式 x'<64hex_enc_key><32hex_salt>'
    扫描进程内存匹配此模式，用 db 文件的 salt 精确定位。

    Args:
        db_path: 数据库文件路径
        callback: 状态回调 callback(message)

    Returns:
        64 字符 hex 密钥，或 None
    """
    if callback:
        callback("读取数据库文件...")
    if not os.path.isfile(db_path) or os.path.getsize(db_path) < PAGE_SZ:
        if callback:
            callback("数据库文件不存在或过小")
        return None

    with open(db_path, "rb") as f:
        db_page1 = f.read(PAGE_SZ)
    db_salt_hex = db_page1[:SALT_SZ].hex()

    if callback:
        callback(f"数据库 salt: {db_salt_hex}")

    # 查找微信进程
    pid = find_wechat_pid()
    if not pid:
        if callback:
            callback("未找到运行中的微信进程")
        return None

    if callback:
        callback(f"微信进程 PID={pid}")

    handle = kernel32.OpenProcess(0x0010 | 0x0400, False, pid)
    if not handle:
        if callback:
            callback("无法打开进程（需要管理员权限）")
        return None

    try:
        regions = enum_regions(handle)
        total_mb = sum(s for _, s in regions) / 1024 / 1024
        if callback:
            callback(f"扫描 {len(regions)} 个内存区域 ({total_mb:.0f}MB)...")

        # 正则匹配 x'<hex>' 模式
        hex_re = re.compile(rb"x'([0-9a-fA-F]{64,192})'")
        key_map = {}  # salt_hex -> enc_key_hex
        t0 = time.time()

        for reg_idx, (base, size) in enumerate(regions):
            data = read_mem(handle, base, size)
            if not data:
                continue

            for m in hex_re.finditer(data):
                hex_str = m.group(1).decode()
                hex_len = len(hex_str)

                if hex_len == 96:
                    # enc_key(64hex) + salt(32hex)
                    enc_key_hex = hex_str[:64]
                    salt_hex = hex_str[64:]
                    if salt_hex == db_salt_hex and salt_hex not in key_map:
                        enc_key = bytes.fromhex(enc_key_hex)
                        if verify_key_for_db(enc_key, db_page1):
                            key_map[salt_hex] = enc_key_hex
                            if callback:
                                elapsed = time.time() - t0
                                callback(f"找到密钥! ({elapsed:.1f}s)")
                            return enc_key_hex

                elif hex_len == 64:
                    # 只有 enc_key，逐个 DB 试
                    enc_key = bytes.fromhex(hex_str)
                    if db_salt_hex not in key_map and verify_key_for_db(enc_key, db_page1):
                        key_map[db_salt_hex] = hex_str
                        if callback:
                            elapsed = time.time() - t0
                            callback(f"找到密钥! ({elapsed:.1f}s)")
                        return hex_str

                elif hex_len > 96 and hex_len % 2 == 0:
                    enc_key_hex = hex_str[:64]
                    salt_hex = hex_str[-32:]
                    if salt_hex == db_salt_hex and salt_hex not in key_map:
                        enc_key = bytes.fromhex(enc_key_hex)
                        if verify_key_for_db(enc_key, db_page1):
                            key_map[salt_hex] = enc_key_hex
                            if callback:
                                elapsed = time.time() - t0
                                callback(f"找到密钥! ({elapsed:.1f}s)")
                            return enc_key_hex

            # 进度
            if callback and (reg_idx + 1) % 500 == 0:
                progress = sum(s for _, s in regions[: reg_idx + 1]) / sum(s for _, s in regions) * 100
                elapsed = time.time() - t0
                callback(f"扫描进度 {progress:.0f}% ({elapsed:.1f}s)...")

        elapsed = time.time() - t0
        if callback:
            callback(f"未找到密钥 ({elapsed:.1f}s)")

        return None
    finally:
        kernel32.CloseHandle(handle)


# ==================== 数据库解密 ====================

def decrypt_database(db_path: str, enc_key_hex: str, out_path: str, callback=None) -> bool:
    """解密 SQLCipher 加密的数据库文件

    Args:
        db_path: 加密的数据库路径
        enc_key_hex: 64 字符 hex 密钥
        out_path: 解密输出路径
        callback: 进度回调 callback(current_page, total_pages)

    Returns:
        是否成功
    """
    enc_key = bytes.fromhex(enc_key_hex)
    file_size = os.path.getsize(db_path)
    total_pages = file_size // PAGE_SZ

    # 读取并验证 page 1
    with open(db_path, "rb") as f:
        page1 = f.read(PAGE_SZ)

    if len(page1) < PAGE_SZ:
        return False

    if not verify_key_for_db(enc_key, page1):
        if callback:
            callback(0, 0)
        return False

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    with open(db_path, "rb") as fin, open(out_path, "wb") as fout:
        for pgno in range(1, total_pages + 1):
            page = fin.read(PAGE_SZ)
            if len(page) < PAGE_SZ:
                if len(page) > 0:
                    page = page + b"\x00" * (PAGE_SZ - len(page))
                else:
                    break

            decrypted = _decrypt_page(enc_key, page, pgno)
            fout.write(decrypted)

            if callback and pgno % 500 == 0:
                callback(pgno, total_pages)

    if callback:
        callback(total_pages, total_pages)
    return True


def _decrypt_page(enc_key, page_data, pgno):
    """解密单个页面"""
    iv = page_data[PAGE_SZ - RESERVE_SZ : PAGE_SZ - RESERVE_SZ + IV_SZ]

    if pgno == 1:
        encrypted = page_data[SALT_SZ : PAGE_SZ - RESERVE_SZ]
        cipher = AES.new(enc_key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(encrypted)
        page = bytearray(SQLITE_HDR + decrypted + b"\x00" * RESERVE_SZ)
        return bytes(page)
    else:
        encrypted = page_data[: PAGE_SZ - RESERVE_SZ]
        cipher = AES.new(enc_key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(encrypted)
        return decrypted + b"\x00" * RESERVE_SZ


# ==================== 便捷接口 ====================

def extract_and_decrypt(db_path: str, out_dir: str = None, callback=None) -> Optional[str]:
    """一键提取密钥并解密数据库

    Returns:
        解密后的数据库路径，或 None
    """
    if out_dir is None:
        out_dir = os.path.join(config.OUTPUT_DIR, "decrypted")
    os.makedirs(out_dir, exist_ok=True)

    db_name = os.path.basename(db_path)
    out_path = os.path.join(out_dir, db_name)

    # 提取密钥
    if callback:
        callback("正在从微信进程内存提取密钥...")
    key = extract_key_for_db(db_path, callback)

    if not key:
        if callback:
            callback("密钥提取失败")
        return None

    if callback:
        callback("密钥提取成功")
        callback("正在解密数据库...")

    # 解密
    def decrypt_progress(current, total):
        if total > 0 and callback:
            callback(f"解密进度: {current}/{total} 页 ({100 * current // total}%)")

    ok = decrypt_database(db_path, key, out_path, decrypt_progress)
    if ok:
        if callback:
            callback(f"解密完成: {out_path}")
        return out_path
    else:
        if callback:
            callback("解密失败")
        return None


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python key_extractor.py <emoticon.db path>")
        sys.exit(1)
    db = sys.argv[1]
    print(f"Target: {db}")
    result = extract_and_decrypt(db, callback=lambda msg: print(f"  {msg}"))
    if result:
        print(f"\nDecrypted: {result}")
    else:
        print("\nFailed")
