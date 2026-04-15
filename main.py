"""微信表情包导入飞书 - 主入口。"""

from __future__ import annotations

import argparse
import os
import sys


def run_gui():
    from gui import run_gui as _run_gui

    _run_gui()


def cmd_extract(args):
    import config
    from wechat_extractor import discover_wechat_users, extract_emojis

    print("=" * 56)
    print("  微信表情包提取")
    print("=" * 56)

    if args.wxid:
        print(f"[信息] 指定微信用户: {args.wxid}")
    else:
        users = discover_wechat_users()
        if users:
            print(f"[信息] 发现微信用户目录: {', '.join(users)}")
        else:
            print(f"[信息] 未在默认路径发现微信用户目录: {config.WECHAT_FILES_ROOT}")

    files = extract_emojis(wxid=args.wxid)
    if files:
        print(f"\n[完成] 成功提取 {len(files)} 个表情")
    else:
        print("\n[失败] 未能提取任何表情")
    return files


def cmd_upload(args):
    import config
    from feishu_uploader import upload_emojis

    emoji_dir = config.EMOJI_OUTPUT_DIR
    if not os.path.isdir(emoji_dir) or not os.listdir(emoji_dir):
        print("[错误] 当前输出目录没有可上传的表情文件，请先执行 extract。")
        return None

    print("=" * 56)
    print("  飞书表情导入")
    print("=" * 56)
    print(f"[信息] 模式: {args.mode}")
    if args.mode == "enterprise":
        print(f"[信息] 表情包名称: {args.pack_name}")

    return upload_emojis(
        emoji_dir=emoji_dir,
        mode=args.mode,
        headless=False,
        pack_name=args.pack_name,
        progress_callback=lambda c, t, m: print(m),
    )


def cmd_full(args):
    files = cmd_extract(args)
    if not files:
        return None

    confirm = input("\n确认将这些表情导入飞书？(y/n): ").strip().lower()
    if confirm != "y":
        print("[已取消] 未执行飞书导入。")
        return None

    return cmd_upload(args)


def cmd_audit(args):
    from feishu_uploader import check_upload_environment
    from wechat_extractor import audit_extraction_pipeline

    print("=" * 56)
    print("  项目链路审计")
    print("=" * 56)

    print("\n[1/2] 微信提取链路")
    extraction = audit_extraction_pipeline(
        wxid=args.wxid,
        sample_downloads=args.samples,
    )

    print("\n[2/2] 飞书上传环境")
    upload_env = check_upload_environment()
    print(upload_env["message"])

    print("\n" + "-" * 56)
    print(f"微信提取可用: {'是' if extraction['ok'] else '否'}")
    print(f"检测账号: {extraction.get('wxid') or '无'}")
    print(f"查询记录数: {extraction.get('emoji_rows', 0)}")
    print(f"样本下载数: {extraction.get('sample_downloaded', 0)}")
    print(f"飞书上传环境就绪: {'是' if upload_env['ok'] else '否'}")
    print("-" * 56)
    return {"extraction": extraction, "upload_env": upload_env}


def run_cli():
    import config

    parser = argparse.ArgumentParser(
        description="微信表情包导入飞书工具 (CLI)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command")

    extract_parser = subparsers.add_parser("extract", help="提取微信表情")
    extract_parser.add_argument("--wxid")

    upload_parser = subparsers.add_parser("upload", help="上传到飞书")
    upload_parser.add_argument("--mode", choices=["personal", "enterprise"], default="personal")
    upload_parser.add_argument("--pack-name", default="微信表情包")

    full_parser = subparsers.add_parser("full", help="提取并导入飞书")
    full_parser.add_argument("--wxid")
    full_parser.add_argument("--mode", choices=["personal", "enterprise"], default="personal")
    full_parser.add_argument("--pack-name", default="微信表情包")

    audit_parser = subparsers.add_parser("audit", help="审计微信提取与飞书上传环境")
    audit_parser.add_argument("--wxid")
    audit_parser.add_argument("--samples", type=int, default=5)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    os.makedirs(config.EMOJI_OUTPUT_DIR, exist_ok=True)

    if args.command == "extract":
        cmd_extract(args)
    elif args.command == "upload":
        cmd_upload(args)
    elif args.command == "full":
        cmd_full(args)
    elif args.command == "audit":
        cmd_audit(args)


def main():
    if "--cli" in sys.argv:
        sys.argv.remove("--cli")
        run_cli()
    else:
        run_gui()


if __name__ == "__main__":
    main()
