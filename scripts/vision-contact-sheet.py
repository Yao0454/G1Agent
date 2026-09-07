"""Render local captured windows for manual, chronological review."""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw

parser = argparse.ArgumentParser()
parser.add_argument("capture", type=Path)
parser.add_argument("output", type=Path)
parser.add_argument("--start", type=int, default=1)
parser.add_argument("--end", type=int, default=10)
args = parser.parse_args()
windows = sorted(args.capture.glob("window-*"))[args.start-1:args.end]
sheet = Image.new("RGB", (720, len(windows)*200), "white")
draw = ImageDraw.Draw(sheet)
for row, window in enumerate(windows):
    draw.text((4, row*200), window.name, fill="black")
    for col, path in enumerate(sorted(window.glob("frame-*.jpg"))):
        with Image.open(path) as image:
            image.thumbnail((240, 180))
            sheet.paste(image, (col*240, row*200+20))
sheet.save(args.output)
