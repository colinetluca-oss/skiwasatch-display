"""Shows the pre-rendered map: no 3D work at all, so it runs on a cheap Pi.

Each time traffic changes we take the saved mountain picture and paint each
route piece in its color, using the saved road shapes as stencils.
"""
import json

import numpy as np
from PIL import Image

from . import config

FOLDER = config.ASSETS / "prerendered"
RANK = {"good": 0, "warn": 1, "bad": 2, "closed": 3}


def available():
    return (FOLDER / "spots.json").exists()


class LightMap:
    def __init__(self, map_w, height):
        self.info = json.loads((FOLDER / "spots.json").read_text())
        size = (map_w, height)
        scale_x, scale_y = map_w / self.info["map_width"], height / self.info["height"]

        def load(name, mode):
            img = Image.open(FOLDER / name).convert(mode)
            return img if img.size == size else img.resize(size, Image.LANCZOS)

        self.base = np.asarray(load("base.jpg", "RGB"), np.float32)
        self.casing = np.asarray(load("casing.png", "L"), np.float32)[..., None] / 255
        # road stencils stay as small 8-bit pictures to save memory on 2 GB Pis
        self.masks = {}
        for p in self.info["pieces"]:
            self.masks[p] = np.asarray(load(p + ".png", "L"))
            self.masks[p + "_dashed"] = np.asarray(load(p + "_dashed.png", "L"))
        # screen positions of pins and peak labels, scaled to this screen
        self.spots = {"peaks": [dict(p, x=p["x"] * scale_x, y=p["y"] * scale_y) for p in self.info["peaks"]],
                      "places": {k: dict(v, x=v["x"] * scale_x, y=v["y"] * scale_y) for k, v in self.info["places"].items()}}
        self._last = None

    def compose(self, levels):
        """Returns the map as an image array (height x width x 3) with roads in their traffic colors."""
        state = tuple(sorted(levels.items()))
        if self._last and self._last[0] == state:
            return self._last[1]
        out = self.base * (1 - 0.85 * self.casing)
        for piece in sorted(self.info["pieces"], key=lambda k: RANK[levels.get(k, "good")]):
            lv = levels.get(piece, "good")
            m = self.masks[piece + "_dashed" if lv == "closed" else piece].astype(np.float32)[..., None] / 255
            color = np.array(config.COLORS["bad" if lv == "closed" else lv], np.float32)
            out = out * (1 - m) + color * m
        img = np.clip(out, 0, 255).astype(np.uint8)
        self._last = (state, img)
        return img
