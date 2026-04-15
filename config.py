"""配置文件：微信表情包导入飞书工具"""

import os
import sys


APP_NAME = "wechatemoji"


def _app_dir() -> str:
    """只读应用目录：源码目录或打包后的 exe 所在目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _data_dir() -> str:
    """用户可写数据目录，避免把状态文件写到 exe 旁边。"""
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return os.path.join(local_appdata, APP_NAME)
    return os.path.join(os.path.expanduser("~"), f".{APP_NAME}")


APP_DIR = _app_dir()
DATA_DIR = _data_dir()

# ==================== 微信相关配置 ====================

# 微信数据根目录（通常在 Documents 下）
WECHAT_FILES_ROOT = os.path.join(os.path.expanduser("~"), "Documents", "WeChat Files")

# V1MMWX 文件头标识
V1MMWX_HEADER = b"V1MMWX"

# AES 解密参数
AES_KEY_SALT = b"saltiest"
AES_KEY_ITERATIONS = 1000
AES_KEY_LENGTH = 32
AES_IV = b"the iv: 16 bytes"
AES_BLOCK_SIZE = 1024

# ==================== 飞书相关配置 ====================

# 飞书主页
FEISHU_HOME_URL = "https://www.feishu.cn/"

# 飞书消息页面（个人表情上传入口）
FEISHU_MESSENGER_URL = "https://www.feishu.cn/messenger/"

# 飞书管理后台
FEISHU_ADMIN_URL = "https://www.feishu.cn/admin"

# 飞书表情规格要求
FEISHU_EMOJI_MAX_SIZE_KB = 800          # 单个表情最大 800KB
FEISHU_EMOJI_DIMENSION = 400             # 推荐尺寸 400×400px
FEISHU_EMOJI_FORMATS = (".png", ".gif", ".jpg", ".jpeg", ".webp")
FEISHU_EMOJI_PACK_MIN = 6                # 表情包最少 6 个
FEISHU_EMOJI_PACK_MAX = 50               # 表情包最多 50 个

# ==================== 输出配置 ====================

OUTPUT_DIR = os.path.join(DATA_DIR, "output")
EMOJI_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "emojis")
DEBUG_DIR = os.path.join(OUTPUT_DIR, "debug")
TMP_DIR = os.path.join(OUTPUT_DIR, "tmp")

# Playwright / Chromium runtime locations
PLAYWRIGHT_BUNDLE_DIR = os.path.join(APP_DIR, "runtime", "ms-playwright")
PLAYWRIGHT_VENDOR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor", "ms-playwright")
PLAYWRIGHT_USER_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Local")),
    "ms-playwright",
)

# Playwright 超时设置（毫秒）
PAGE_TIMEOUT = 30000
UPLOAD_TIMEOUT = 10000
LOGIN_TIMEOUT = 120000  # 登录扫码等待 2 分钟
