"""
飞书表情上传 API 嗅探工具。

运行后打开飞书浏览器，手动上传一次表情，
脚本会把完整的请求/响应记录到 debug 目录中的 sniff_output.txt。
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import TextIO

from playwright.sync_api import sync_playwright

import config


OUTPUT_FILE = Path(config.DEBUG_DIR) / "sniff_output.txt"
BROWSER_SNIFFER_DIR = Path(config.TMP_DIR) / "browser_sniffer"

KEYWORDS = [
    "emoji",
    "emoticon",
    "sticker",
    "image",
    "upload",
    "file",
    "im/v1",
    "im/v2",
    "resource",
    "media",
    "表情",
    "贴纸",
]


def is_interesting(url: str) -> bool:
    url_lower = url.lower()
    return any(keyword in url_lower for keyword in KEYWORDS)


def log(handle: TextIO, message: str) -> None:
    print(message)
    handle.write(message + "\n")
    handle.flush()


def main() -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    BROWSER_SNIFFER_DIR.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as handle:
        log(handle, f"=== 飞书 API 嗅探开始 {datetime.now()} ===\n")

        with sync_playwright() as playwright:
            # 用持久化 context，保留登录态，便于连续复现上传链路。
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(BROWSER_SNIFFER_DIR),
                headless=False,
                viewport={"width": 1280, "height": 800},
                args=["--disable-blink-features=AutomationControlled"],
            )
            page = context.pages[0] if context.pages else context.new_page()

            captured: list[dict[str, object]] = []

            def on_request(request) -> None:
                url = request.url
                if not is_interesting(url):
                    return
                entry = {
                    "type": "REQUEST",
                    "time": datetime.now().strftime("%H:%M:%S.%f"),
                    "method": request.method,
                    "url": url,
                    "headers": dict(request.headers),
                    "post_data": request.post_data,
                }
                captured.append(entry)
                log(handle, f"\n>>> REQUEST [{request.method}] {url}")
                if request.post_data:
                    log(handle, f"    Body: {request.post_data[:500]}")

            def on_response(response) -> None:
                url = response.url
                if not is_interesting(url):
                    return
                try:
                    body = response.text()
                except Exception:
                    body = "<binary or error>"
                entry = {
                    "type": "RESPONSE",
                    "time": datetime.now().strftime("%H:%M:%S.%f"),
                    "status": response.status,
                    "url": url,
                    "body": body[:2000],
                }
                captured.append(entry)
                log(handle, f"<<< RESPONSE [{response.status}] {url}")
                log(handle, f"    Body: {body[:500]}")

            page.on("request", on_request)
            page.on("response", on_response)

            log(handle, "打开飞书消息页...")
            page.goto("https://www.feishu.cn/messenger/", wait_until="domcontentloaded")
            time.sleep(2)

            print("\n" + "=" * 60)
            print("请在浏览器中手动完成以下操作：")
            print("1. 点击任意一个聊天会话")
            print("2. 点击输入框旁边的表情按钮 (😊)")
            print("3. 切换到「自定义」或「贴纸」Tab")
            print("4. 点击「添加」或「+」按钮")
            print("5. 选择一张表情图片上传")
            print("6. 完成上传后按 Enter 键退出")
            print("=" * 60 + "\n")

            input("完成上传后按 Enter 退出...\n")

            log(handle, f"\n\n=== 完整捕获记录 ({len(captured)} 条) ===")
            for entry in captured:
                log(handle, json.dumps(entry, ensure_ascii=False, indent=2))

            context.close()

        log(handle, f"\n=== 嗅探结束 {datetime.now()} ===")
    print(f"\n结果已保存到: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
