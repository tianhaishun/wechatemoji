"""
飞书表情上传 API 嗅探工具
运行后打开飞书浏览器，手动上传一次表情，脚本会把完整的请求/响应记录到 sniff_output.txt
"""
import json
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

OUTPUT_FILE = "sniff_output.txt"

KEYWORDS = [
    "emoji", "emoticon", "sticker", "image", "upload", "file",
    "im/v1", "im/v2", "resource", "media",
    "表情", "贴纸",
]

def is_interesting(url: str) -> bool:
    url_lower = url.lower()
    return any(k in url_lower for k in KEYWORDS)

def log(f, msg: str):
    print(msg)
    f.write(msg + "\n")
    f.flush()

def main():
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        log(f, f"=== 飞书 API 嗅探开始 {datetime.now()} ===\n")

        with sync_playwright() as p:
            # 用持久化 context，保留登录态
            context = p.chromium.launch_persistent_context(
                user_data_dir="output/browser_sniffer",
                headless=False,
                viewport={"width": 1280, "height": 800},
                args=["--disable-blink-features=AutomationControlled"],
            )
            page = context.pages[0] if context.pages else context.new_page()

            captured = []

            def on_request(request):
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
                log(f, f"\n>>> REQUEST [{request.method}] {url}")
                if request.post_data:
                    log(f, f"    Body: {request.post_data[:500]}")

            def on_response(response):
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
                log(f, f"<<< RESPONSE [{response.status}] {url}")
                log(f, f"    Body: {body[:500]}")

            page.on("request", on_request)
            page.on("response", on_response)

            log(f, "打开飞书消息页...")
            page.goto("https://www.feishu.cn/messenger/", wait_until="domcontentloaded")
            time.sleep(2)

            print("\n" + "="*60)
            print("请在浏览器中手动完成以下操作：")
            print("1. 点击任意一个聊天会话")
            print("2. 点击输入框旁边的表情按钮 (😊)")
            print("3. 切换到「自定义」或「贴纸」Tab")
            print("4. 点击「添加」或「+」按钮")
            print("5. 选择一张表情图片上传")
            print("6. 完成上传后按 Enter 键退出")
            print("="*60 + "\n")

            input("完成上传后按 Enter 退出...\n")

            # 保存完整结果
            log(f, f"\n\n=== 完整捕获记录 ({len(captured)} 条) ===")
            for entry in captured:
                log(f, json.dumps(entry, ensure_ascii=False, indent=2))

            context.close()

        log(f, f"\n=== 嗅探结束 {datetime.now()} ===")
    print(f"\n结果已保存到: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
