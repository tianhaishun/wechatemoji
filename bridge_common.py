"""Shared helpers for gui.py and tauri_bridge.py.

Eliminates code duplication between the two bridge implementations.
"""

from __future__ import annotations

import base64
import os
from io import BytesIO
from pathlib import Path
from typing import Any

import config


def normalize_user(info: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw WeChat user info dict into a standard format."""
    wxid = info.get("wxid", "")
    nickname = info.get("nickname", "")
    label = f"{nickname} ({wxid})" if nickname else wxid
    return {
        "label": label,
        "wxid": wxid,
        "wx_dir": info.get("wx_dir", ""),
        "nickname": nickname,
        "running": bool(info.get("running")),
    }


def build_upload_env_detail(env: dict[str, Any]) -> str:
    """Build a human-readable summary of upload environment status."""
    parts = []
    parts.append("playwright installed" if env.get("python_package") else "playwright missing")
    parts.append("chromium runtime available" if env.get("browser_runtime") else "chromium runtime missing")
    return ", ".join(parts)


def collect_emoji_files(folder: str) -> list[str]:
    """Recursively collect supported emoji files from a folder."""
    supported = {ext.lower() for ext in config.FEISHU_EMOJI_FORMATS}
    files = []
    for path in Path(folder).rglob("*"):
        if path.is_file() and path.suffix.lower() in supported:
            files.append(str(path))
    files.sort()
    return files


def emit_db_path_for_user(emit_fn, user: dict[str, Any]) -> None:
    """Detect and emit the emoticon.db path for a given user.

    Args:
        emit_fn: Callable(event_name, data) — either gui._emit or ctx.emit
        user: Normalized user dict with 'wx_dir' key
    """
    try:
        from wechat_extractor import find_emoticon_db
    except ImportError:
        emit_fn("dbPath", {"text": "wechat_extractor module not available", "ok": False})
        return

    wx_dir = user.get("wx_dir", "")
    db_path = find_emoticon_db(wx_dir) if wx_dir else None
    if db_path:
        emit_fn("dbPath", {"text": db_path, "ok": True})
    elif wx_dir:
        emit_fn("dbPath", {"text": f"{wx_dir} (emoticon.db not found)", "ok": False})
    else:
        emit_fn("dbPath", {"text": "no wechat data dir for this account", "ok": False})


def load_emoji_thumbs(emit_fn, files: list[str], batch_size: int = 20) -> None:
    """Generate thumbnails in batches and emit them via emit_fn.

    Args:
        emit_fn: Callable(event_name, data)
        files: List of emoji file paths
        batch_size: Number of thumbnails per batch emission
    """
    from PIL import Image

    emit_fn("emojiList", [])  # clear old list

    batch: list[dict] = []
    for filepath in files:
        try:
            image = Image.open(filepath)
            try:
                image.seek(0)
            except (AttributeError, EOFError):
                pass
            image = image.convert("RGBA")
            image.thumbnail((80, 80))
            buffer = BytesIO()
            bg = Image.new("RGB", image.size, (255, 255, 255))
            bg.paste(image, mask=image.getchannel("A"))
            bg.save(buffer, format="JPEG", quality=72)
            thumb = base64.b64encode(buffer.getvalue()).decode("ascii")
            batch.append(
                {
                    "file": filepath,
                    "name": os.path.basename(filepath),
                    "size_kb": round(os.path.getsize(filepath) / 1024, 1),
                    "thumb": f"data:image/jpeg;base64,{thumb}",
                }
            )
            if len(batch) >= batch_size:
                emit_fn("emojiListAppend", batch)
                batch = []
        except Exception:
            continue

    if batch:
        emit_fn("emojiListAppend", batch)
    emit_fn("emojiListReady", len(files))


def pause_signal_path() -> str:
    """Path to the extraction pause signal file."""
    return os.path.join(config.OUTPUT_DIR, ".pause_extract")


def stop_upload_signal_path() -> str:
    """Path to the upload stop signal file."""
    return os.path.join(config.OUTPUT_DIR, ".stop_upload")
