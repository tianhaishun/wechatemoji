"""Generate playful app mascot and Windows icon assets."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parent.parent
WEB_ASSETS = ROOT / "web" / "assets"
TAURI_ICONS = ROOT / "tauri_app" / "src-tauri" / "icons"

MASTER_SIZE = 1024
MASTER_OUTPUT = WEB_ASSETS / "app-mascot.png"

PNG_TARGETS = {
    "icon.png": 512,
    "32x32.png": 32,
    "128x128.png": 128,
    "128x128@2x.png": 256,
    "Square30x30Logo.png": 30,
    "Square44x44Logo.png": 44,
    "Square71x71Logo.png": 71,
    "Square89x89Logo.png": 89,
    "Square107x107Logo.png": 107,
    "Square142x142Logo.png": 142,
    "Square150x150Logo.png": 150,
    "Square284x284Logo.png": 284,
    "Square310x310Logo.png": 310,
    "StoreLogo.png": 50,
}

ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def blend_color(start: tuple[int, int, int, int], end: tuple[int, int, int, int], t: float) -> tuple[int, int, int, int]:
    return tuple(lerp(sa, ea, t) for sa, ea in zip(start, end))


def make_diagonal_gradient(size: int, start: tuple[int, int, int, int], end: tuple[int, int, int, int]) -> Image.Image:
    img = Image.new("RGBA", (size, size))
    pixels = img.load()
    scale = max((size - 1) * 2, 1)
    for y in range(size):
        for x in range(size):
            t = (x + y) / scale
            pixels[x, y] = blend_color(start, end, t)
    return img


def add_shadow(base: Image.Image, alpha_mask: Image.Image, offset: tuple[int, int], blur: int, color: tuple[int, int, int, int]) -> None:
    mask = Image.new("L", base.size, 0)
    mask.paste(alpha_mask, offset)
    shadow = Image.new("RGBA", base.size, color)
    shadow.putalpha(mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    base.alpha_composite(shadow)


def rounded_rect_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def draw_bubble(layer: Image.Image, box: tuple[int, int, int, int], fill: tuple[int, int, int, int], outline: tuple[int, int, int, int]) -> None:
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle(box, radius=int((box[2] - box[0]) * 0.2), fill=fill, outline=outline, width=16)
    tail = [
        (box[0] + 26, box[3] - 46),
        (box[0] - 30, box[3] + 18),
        (box[0] + 82, box[3] - 8),
    ]
    draw.polygon(tail, fill=fill, outline=outline)
    for idx, dx in enumerate((0.28, 0.5, 0.72)):
        cx = int(box[0] + (box[2] - box[0]) * dx)
        cy = int(box[1] + (box[3] - box[1]) * 0.48)
        radius = 26 if idx == 1 else 22
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(255, 255, 255, 235))


def draw_heart(draw: ImageDraw.ImageDraw, center: tuple[int, int], size: int, fill: tuple[int, int, int, int], outline: tuple[int, int, int, int]) -> None:
    x, y = center
    r = size // 3
    draw.ellipse((x - size // 2, y - r * 2, x - size // 2 + 2 * r, y), fill=fill, outline=outline, width=10)
    draw.ellipse((x - 2, y - r * 2, x - 2 + 2 * r, y), fill=fill, outline=outline, width=10)
    draw.polygon([(x - size // 2 - 8, y - r), (x + size // 2 + 8, y - r), (x, y + size // 2 + 10)], fill=fill, outline=outline)


def draw_sparkle(draw: ImageDraw.ImageDraw, center: tuple[int, int], size: int, fill: tuple[int, int, int, int], outline: tuple[int, int, int, int]) -> None:
    x, y = center
    points = [
        (x, y - size),
        (x + size // 3, y - size // 3),
        (x + size, y),
        (x + size // 3, y + size // 3),
        (x, y + size),
        (x - size // 3, y + size // 3),
        (x - size, y),
        (x - size // 3, y - size // 3),
    ]
    draw.polygon(points, fill=fill, outline=outline)


def draw_face(layer: Image.Image, center: tuple[int, int], radius: int) -> None:
    draw = ImageDraw.Draw(layer)
    x, y = center

    draw.ellipse((x - radius - 22, y - radius - 22, x + radius + 22, y + radius + 22), fill=(255, 255, 255, 245))
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(255, 213, 107, 255), outline=(119, 83, 32, 255), width=16)

    eye_y = y - radius // 4
    eye_offset = radius // 2
    draw.arc((x - eye_offset - 48, eye_y - 18, x - eye_offset + 8, eye_y + 30), start=205, end=345, fill=(100, 70, 34, 255), width=12)
    draw.arc((x + eye_offset - 8, eye_y - 18, x + eye_offset + 48, eye_y + 30), start=195, end=335, fill=(100, 70, 34, 255), width=12)

    mouth_box = (x - radius // 2, y - 10, x + radius // 2, y + radius // 2)
    draw.arc(mouth_box, start=18, end=162, fill=(111, 58, 44, 255), width=18)

    blush = (255, 160, 176, 170)
    draw.ellipse((x - radius + 60, y + 8, x - radius + 140, y + 72), fill=blush)
    draw.ellipse((x + radius - 140, y + 8, x + radius - 60, y + 72), fill=blush)


def build_master_icon(size: int = MASTER_SIZE) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shell_size = size - 64

    background = make_diagonal_gradient(shell_size, (255, 245, 197, 255), (255, 186, 160, 255))
    background_draw = ImageDraw.Draw(background)
    background_draw.ellipse((70, 70, 470, 470), fill=(255, 255, 255, 70))
    background_draw.ellipse((500, 90, 860, 460), fill=(126, 203, 255, 70))
    background_draw.ellipse((150, 520, 560, 900), fill=(116, 211, 189, 60))
    background_draw.ellipse((560, 560, 900, 900), fill=(255, 126, 168, 48))

    shell_mask = rounded_rect_mask((shell_size, shell_size), radius=220)
    shell_layer = Image.new("RGBA", (shell_size, shell_size), (0, 0, 0, 0))
    shell_layer.alpha_composite(background)
    shell = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shell.paste(shell_layer, (32, 32), shell_mask)
    canvas.alpha_composite(shell)

    border = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    border_draw = ImageDraw.Draw(border)
    border_draw.rounded_rectangle((32, 32, size - 32, size - 32), radius=220, outline=(255, 255, 255, 190), width=20)
    canvas.alpha_composite(border)

    confetti = ImageDraw.Draw(canvas)
    for box, fill in (
        ((156, 198, 192, 234), (255, 255, 255, 180)),
        ((760, 220, 810, 270), (255, 255, 255, 170)),
        ((820, 740, 854, 774), (255, 255, 255, 165)),
        ((224, 804, 260, 840), (255, 255, 255, 155)),
    ):
        confetti.ellipse(box, fill=fill)

    bubble = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bubble_mask = Image.new("L", (size, size), 0)
    bubble_mask_draw = ImageDraw.Draw(bubble_mask)
    bubble_box = (546, 250, 880, 548)
    bubble_mask_draw.rounded_rectangle(bubble_box, radius=82, fill=255)
    bubble_mask_draw.polygon([(570, 498), (518, 596), (646, 538)], fill=255)
    add_shadow(canvas, bubble_mask, (0, 22), blur=34, color=(96, 159, 147, 92))
    draw_bubble(bubble, bubble_box, fill=(116, 211, 189, 255), outline=(76, 144, 133, 255))
    canvas.alpha_composite(bubble)

    face = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    face_mask = Image.new("L", (size, size), 0)
    face_mask_draw = ImageDraw.Draw(face_mask)
    face_center = (416, 600)
    face_radius = 208
    face_mask_draw.ellipse((face_center[0] - face_radius - 28, face_center[1] - face_radius - 28, face_center[0] + face_radius + 28, face_center[1] + face_radius + 28), fill=255)
    add_shadow(canvas, face_mask, (0, 28), blur=44, color=(168, 113, 68, 84))
    draw_face(face, face_center, face_radius)
    canvas.alpha_composite(face)

    deco = ImageDraw.Draw(canvas)
    draw_heart(deco, (246, 286), 130, fill=(255, 126, 168, 255), outline=(181, 66, 108, 255))
    draw_sparkle(deco, (770, 700), 74, fill=(255, 234, 154, 255), outline=(178, 132, 44, 255))
    draw_sparkle(deco, (220, 730), 42, fill=(255, 255, 255, 220), outline=(178, 144, 98, 180))

    return canvas


def save_assets(master: Image.Image) -> None:
    WEB_ASSETS.mkdir(parents=True, exist_ok=True)
    TAURI_ICONS.mkdir(parents=True, exist_ok=True)

    master.save(MASTER_OUTPUT)

    for filename, px in PNG_TARGETS.items():
        master.resize((px, px), Image.Resampling.LANCZOS).save(TAURI_ICONS / filename)

    master.save(TAURI_ICONS / "icon.ico", sizes=ICO_SIZES)
    try:
        master.save(TAURI_ICONS / "icon.icns")
    except OSError:
        pass


def main() -> None:
    master = build_master_icon()
    save_assets(master)
    print(f"Generated mascot assets at {MASTER_OUTPUT}")


if __name__ == "__main__":
    main()
