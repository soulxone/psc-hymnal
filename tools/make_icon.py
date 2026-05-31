"""Generate a multi-resolution Windows .ico for PSC Hymnal from the logo PNG."""
from pathlib import Path

from PIL import Image

SRC = Path(r"D:\ps-church_com\fb_app_icon_1024_mint.png")
OUT = Path(__file__).resolve().parent.parent / "hymnal.ico"

img = Image.open(SRC).convert("RGBA")
# Square-crop center if needed.
w, h = img.size
if w != h:
    s = min(w, h)
    img = img.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2))

sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
img.save(OUT, format="ICO", sizes=sizes)
print("wrote", OUT, "sizes:", sizes)
