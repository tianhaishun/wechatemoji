from __future__ import annotations

import shutil
from pathlib import Path

import config


REQUIRED_PATTERNS = ("chromium-*", "chromium_headless_shell-*", "ffmpeg-*", "winldd-*")


def main() -> int:
    src = Path(config.PLAYWRIGHT_USER_DIR)
    dst = Path(config.PLAYWRIGHT_VENDOR_DIR)

    if not src.exists():
        print(f"[error] Playwright runtime cache not found: {src}")
        return 1

    dst.mkdir(parents=True, exist_ok=True)
    copied = 0
    for pattern in REQUIRED_PATTERNS:
        matches = list(src.glob(pattern))
        if not matches:
            print(f"[warn] missing pattern in local cache: {pattern}")
            continue
        for item in matches:
            target = dst / item.name
            print(f"[copy] {item} -> {target}")
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target)
            copied += 1

    if copied == 0:
        print("[error] no runtime directories were copied")
        return 1

    print(f"[done] staged Playwright runtime into: {dst}")
    print("[hint] rebuild the onedir package after staging so the app ships with Chromium.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
