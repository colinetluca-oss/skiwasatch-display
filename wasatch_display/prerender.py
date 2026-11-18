"""Draws the 3D view once and saves it as pictures, so a small, cheap Pi can
show it without doing any 3D work.

The camera never moves, so the mountains look the same every minute. Only the
road colors change. So we save:
  base.jpg            the 3D view with no traffic colors
  casing.png          where the dark edges of the routes are
  <piece>.png         where each route piece is (white = road)
  <piece>_dashed.png  the same, as a dashed line (used when a road is closed)
  spots.json          where each resort, Home and peak lands on screen
The display then just colors those road shapes and stacks the pictures.

Run this on any computer with a graphics card (or in the cloud):
    python -m wasatch_display.prerender --size 1920x1080
"""
import argparse
import json

import moderngl
from PIL import Image

from . import config
from .terrain import Terrain

OUT = config.ASSETS / "prerendered"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", default="1920x1080")
    args = ap.parse_args()
    w, h = map(int, args.size.lower().split("x"))
    map_w = round(w * config.MAP_SHARE)

    ctx = moderngl.create_standalone_context(require=310)
    fbo = ctx.simple_framebuffer((map_w, h))
    t = Terrain(ctx)
    OUT.mkdir(parents=True, exist_ok=True)

    def grab(mode):
        data = fbo.read(components=3)
        img = Image.frombytes("RGB", (map_w, h), data).transpose(Image.FLIP_TOP_BOTTOM)
        return img if mode == "RGB" else img.convert("L")

    fbo.clear(0, 0, 0, 1)
    proj, view = t.render_map(fbo, map_w, h, image=t.base_image)
    grab("RGB").save(OUT / "base.jpg", quality=92)

    def mask(img, name):
        fbo.clear(0, 0, 0, 1)
        t.render_map(fbo, map_w, h, image=img, fog=False, sky=False)
        grab("L").save(OUT / f"{name}.png", optimize=True)

    mask(t.route_mask(width=9), "casing")
    for piece in t.routes:
        mask(t.route_mask(piece), piece)
        mask(t.route_mask(piece, dashed=True), piece + "_dashed")

    spots = t.spots(proj, view, map_w, h)
    spots.update({"width": w, "height": h, "map_width": map_w, "pieces": list(t.routes)})
    (OUT / "spots.json").write_text(json.dumps(spots, indent=1))
    print("saved pre-rendered map to", OUT)


if __name__ == "__main__":
    main()
