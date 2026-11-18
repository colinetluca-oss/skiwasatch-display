"""Draws the 3D Wasatch with OpenGL (through the moderngl library).

How it works, in short:
1. heights.npy is a grid of real elevations (meters). We turn it into a
   mesh: a big sheet of triangles bent up and down by those heights.
2. color.jpg is a picture of the range from above (snow, trees, rock,
   shading and the grey street grid). It's stretched over the mesh like a
   decal; this is called a texture.
3. The colored traffic routes are painted onto a copy of that picture,
   so they follow the ground exactly.
4. A virtual camera floats over the valley, looks east and tilts down.
   The graphics card works out what the camera sees.
"""
import json
import math

import numpy as np
from PIL import Image, ImageDraw
import moderngl

from . import config

ROAD_RGB = {"good": config.COLORS["good"], "warn": config.COLORS["warn"],
            "bad": config.COLORS["bad"], "closed": config.COLORS["bad"]}
RANK = {"good": 0, "warn": 1, "bad": 2, "closed": 3}
BASE_ELEVATION = 1220  # meters; the valley floor sits near zero in our 3D world

TERRAIN_VS = """
#version 140
in vec2 in_uv;
in float in_h;
uniform mat4 mvp;
uniform mat4 view;
uniform vec2 size;
uniform float stretch;
uniform float base;
out vec2 uv;
out float depth;
void main() {
    vec3 pos = vec3((in_uv.x - 0.5) * size.x, (in_h - base) * stretch, (in_uv.y - 0.5) * size.y);
    uv = in_uv;
    depth = -(view * vec4(pos, 1.0)).z;      // distance from camera, for fog
    gl_Position = mvp * vec4(pos, 1.0);
}
"""
TERRAIN_FS = """
#version 140
in vec2 uv;
in float depth;
uniform sampler2D tex;
uniform vec3 fog_color;
uniform vec2 fog_range;
uniform vec3 flat_color;
uniform bool use_flat;
out vec4 color;
void main() {
    vec3 c = use_flat ? flat_color : texture(tex, uv).rgb;
    float f = clamp((depth - fog_range.x) / (fog_range.y - fog_range.x), 0.0, 1.0);
    color = vec4(mix(c, fog_color, f), 1.0);
}
"""
QUAD_VS = """
#version 140
in vec2 in_pos;
out vec2 uv;
void main() { uv = in_pos * 0.5 + 0.5; gl_Position = vec4(in_pos, 0.0, 1.0); }
"""
SKY_FS = """
#version 140
in vec2 uv;
uniform vec3 top;
uniform vec3 low;
out vec4 color;
void main() { float t = clamp((1.0 - uv.y) / 0.42, 0.0, 1.0); color = vec4(mix(top, low, t), 1.0); }
"""
OVERLAY_FS = """
#version 140
in vec2 uv;
uniform sampler2D tex;
out vec4 color;
void main() { color = texture(tex, vec2(uv.x, 1.0 - uv.y)); }
"""


def _rgb(c):
    return tuple(v / 255 for v in c)


def perspective(fovy_deg, aspect, near, far):
    f = 1 / math.tan(math.radians(fovy_deg) / 2)
    m = np.zeros((4, 4))
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = 2 * far * near / (near - far)
    m[3, 2] = -1
    return m


def look_at(eye, target, up=(0, 1, 0)):
    eye, target, up = map(np.asarray, (eye, target, up))
    f = target - eye; f = f / np.linalg.norm(f)
    s = np.cross(f, up); s = s / np.linalg.norm(s)
    u = np.cross(s, f)
    m = np.identity(4)
    m[0, :3], m[1, :3], m[2, :3] = s, u, -f
    m[:3, 3] = -m[:3, :3] @ eye
    return m


class Terrain:
    def __init__(self, ctx: moderngl.Context):
        self.ctx = ctx
        folder = config.ASSETS / "terrain"
        self.meta = json.loads((folder / "meta.json").read_text())
        self.routes = json.loads((folder / "routes.json").read_text())
        self.heights = np.load(folder / "heights.npy").astype(np.float32)
        self.base_image = Image.open(folder / "color.jpg").convert("RGB")
        self.gh, self.gw = self.heights.shape
        self.size = (self.meta["wm"], self.meta["hm_m"])
        self._road_state = None

        # --- the mesh: one vertex per height sample, two triangles per grid square
        v, u = np.mgrid[0:self.gh, 0:self.gw]
        uv = np.stack([u / (self.gw - 1), v / (self.gh - 1)], -1).reshape(-1, 2).astype("f4")
        h = self.heights.reshape(-1, 1)
        verts = np.hstack([uv, h]).astype("f4")
        i = np.arange(self.gh * self.gw).reshape(self.gh, self.gw)
        a, b, c, d = i[:-1, :-1], i[:-1, 1:], i[1:, :-1], i[1:, 1:]
        idx = np.stack([a, c, b, b, c, d], -1).reshape(-1).astype("u4")

        self.prog = ctx.program(vertex_shader=TERRAIN_VS, fragment_shader=TERRAIN_FS)
        self.vao = ctx.vertex_array(self.prog, [(ctx.buffer(verts.tobytes()), "2f 1f", "in_uv", "in_h")],
                                    ctx.buffer(idx.tobytes()))
        # a dark floor far beyond the edges, so the terrain never floats in the sky
        W, H = self.size
        floor = np.array([[-1.5, -1.5, BASE_ELEVATION - 4], [2.5, -1.5, BASE_ELEVATION - 4], [-1.5, 2.5, BASE_ELEVATION - 4],
                          [2.5, -1.5, BASE_ELEVATION - 4], [2.5, 2.5, BASE_ELEVATION - 4], [-1.5, 2.5, BASE_ELEVATION - 4]], "f4")
        self.floor = ctx.vertex_array(self.prog, [(ctx.buffer(floor.tobytes()), "2f 1f", "in_uv", "in_h")])

        self.tex = ctx.texture(self.base_image.size, 3, self.base_image.tobytes())
        self.tex.build_mipmaps()
        self.tex.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
        try:
            self.tex.anisotropy = 16.0   # keeps the far mountains sharp at a low angle
        except Exception:
            pass

        quad = np.array([-1, -1, 1, -1, -1, 1, 1, 1], "f4")
        qbuf = ctx.buffer(quad.tobytes())
        self.sky_prog = ctx.program(vertex_shader=QUAD_VS, fragment_shader=SKY_FS)
        self.sky = ctx.vertex_array(self.sky_prog, [(qbuf, "2f", "in_pos")])
        self.ov_prog = ctx.program(vertex_shader=QUAD_VS, fragment_shader=OVERLAY_FS)
        self.ov = ctx.vertex_array(self.ov_prog, [(qbuf, "2f", "in_pos")])
        self.ov_tex = None

    # ---------- geometry helpers
    def height_at(self, u, v):
        x = min(max(u * (self.gw - 1), 0), self.gw - 1)
        y = min(max(v * (self.gh - 1), 0), self.gh - 1)
        x0, y0 = int(x), int(y)
        x1, y1 = min(x0 + 1, self.gw - 1), min(y0 + 1, self.gh - 1)
        fx, fy = x - x0, y - y0
        h = self.heights
        return (h[y0, x0] * (1 - fx) + h[y0, x1] * fx) * (1 - fy) + (h[y1, x0] * (1 - fx) + h[y1, x1] * fx) * fy

    def world(self, u, v, lift=0.0):
        return np.array([(u - .5) * self.size[0],
                         (self.height_at(u, v) - BASE_ELEVATION) * config.HEIGHT_STRETCH + lift,
                         (v - .5) * self.size[1]])

    def camera(self, width, height, pitch=config.PITCH_DEGREES):
        p = math.radians(pitch)
        target = self.world(.465, .485)
        forward = np.array([math.sin(p), -math.cos(p), 0.0])   # east, tilted down
        dist = 33000 + (pitch - 55) * 280
        eye = target - forward * dist
        view = look_at(eye, target)
        proj = perspective(config.FIELD_OF_VIEW, width / height, 500, 200000)
        return proj, view

    def project(self, points, proj, view, width, height):
        """3D points -> screen pixels (x, y) plus whether each is in front of the camera."""
        P = np.hstack([np.asarray(points), np.ones((len(points), 1))]) @ (proj @ view).T
        ndc = P[:, :3] / P[:, 3:4]
        sx = (ndc[:, 0] + 1) / 2 * width
        sy = (1 - ndc[:, 1]) / 2 * height
        visible = (P[:, 3] > 0) & (np.abs(ndc[:, 0]) < 1.05) & (np.abs(ndc[:, 1]) < 1.05)
        return np.stack([sx, sy], 1), visible

    def spots(self, proj, view, width, height):
        """Where each peak and place appears on screen, in pixels of the map area."""
        peaks = self.meta["peaks"]
        xy, vis = self.project([self.world(*p["uv"], 30) for p in peaks], proj, view, width, height)
        out = {"peaks": [{"name": p["n"], "ft": p["ft"], "x": float(x), "y": float(y), "visible": bool(v)}
                         for p, (x, y), v in zip(peaks, xy, vis)], "places": {}}
        keys = list(self.meta["places"])
        xy, vis = self.project([self.world(*self.meta["places"][k], 30) for k in keys], proj, view, width, height)
        for k, (x, y), v in zip(keys, xy, vis):
            out["places"][k] = {"x": float(x), "y": float(y), "visible": bool(v)}
        return out

    # ---------- roads
    def paint_roads(self, levels):
        """Paint the traffic routes onto the ground picture in their current colors."""
        state = tuple(sorted(levels.items()))
        if state == self._road_state:
            return
        self._road_state = state
        img = self.base_image.copy()
        draw = ImageDraw.Draw(img)
        Wt, Ht = img.size
        order = sorted(self.routes, key=lambda k: RANK[levels.get(k, "good")])
        lines = {k: [[(u * Wt, v * Ht) for u, v in line] for line in self.routes[k]] for k in order}
        for k in order:                                  # dark edge first, so colors pop
            for pts in lines[k]:
                draw.line(pts, fill=(4, 7, 11), width=9, joint="curve")
        for k in order:
            lv = levels.get(k, "good")
            for pts in lines[k]:
                if lv == "closed":
                    _dashed(draw, pts, ROAD_RGB[lv], width=6, on=5, off=12)
                else:
                    draw.line(pts, fill=ROAD_RGB[lv], width=5, joint="curve")
        self.tex.write(img.tobytes())
        self.tex.build_mipmaps()

    # ---------- drawing
    def render_map(self, fbo, map_w, screen_h, image=None, fog=True, sky=True):
        """Draw the 3D map into the left part of `fbo`. Optionally swap in a different ground picture."""
        ctx = self.ctx
        if image is not None:
            self.tex.write(image.tobytes())
            self.tex.build_mipmaps()
            self._road_state = None
        fbo.use()
        ctx.viewport = (0, 0, map_w, screen_h)
        ctx.disable(moderngl.DEPTH_TEST)
        if sky:
            self.sky_prog["top"].value = _rgb(config.COLORS["sky_top"])
            self.sky_prog["low"].value = _rgb(config.COLORS["sky_low"])
            self.sky.render(moderngl.TRIANGLE_STRIP)
        proj, view = self.camera(map_w, screen_h)
        ctx.enable(moderngl.DEPTH_TEST)
        self.prog["mvp"].write((proj @ view).T.astype("f4").tobytes())
        self.prog["view"].write(view.T.astype("f4").tobytes())
        self.prog["size"].value = self.size
        self.prog["stretch"].value = config.HEIGHT_STRETCH
        self.prog["base"].value = BASE_ELEVATION
        self.prog["fog_color"].value = _rgb(config.COLORS["sky_low"])
        self.prog["fog_range"].value = (45000.0, 85000.0) if fog else (1e9, 2e9)
        self.tex.use(0)
        self.prog["tex"].value = 0
        self.prog["use_flat"].value = True
        self.prog["flat_color"].value = _rgb(config.COLORS["panel"]) if sky else (0.0, 0.0, 0.0)
        self.floor.render(moderngl.TRIANGLES)
        self.prog["use_flat"].value = False
        self.vao.render(moderngl.TRIANGLES)
        ctx.disable(moderngl.DEPTH_TEST)
        return proj, view

    def render(self, fbo, map_w, screen_h, overlay_rgba, screen_w):
        ctx = self.ctx
        fbo.use()
        ctx.viewport = (0, 0, screen_w, screen_h)
        fbo.clear(*_rgb(config.COLORS["night"]), 1.0)
        proj, view = self.render_map(fbo, map_w, screen_h)
        # panel, pins and labels on top, as one see-through picture
        ctx.viewport = (0, 0, screen_w, screen_h)
        if self.ov_tex is None or self.ov_tex.size != (screen_w, screen_h):
            self.ov_tex = ctx.texture((screen_w, screen_h), 4)
        self.ov_tex.write(overlay_rgba)
        ctx.enable(moderngl.BLEND)
        ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self.ov_tex.use(0)
        self.ov_prog["tex"].value = 0
        self.ov.render(moderngl.TRIANGLE_STRIP)
        ctx.disable(moderngl.BLEND)
        return proj, view

    def route_mask(self, piece=None, width=5, dashed=False):
        """A black picture with one route (or all routes, if piece is None) drawn in white."""
        img = Image.new("RGB", self.base_image.size, (0, 0, 0))
        draw = ImageDraw.Draw(img)
        Wt, Ht = img.size
        for k in ([piece] if piece else list(self.routes)):
            for line in self.routes[k]:
                pts = [(u * Wt, v * Ht) for u, v in line]
                if dashed:
                    _dashed(draw, pts, (255, 255, 255), width=width + 1, on=5, off=12)
                else:
                    draw.line(pts, fill=(255, 255, 255), width=width, joint="curve")
        return img


def _dashed(draw, pts, fill, width, on, off):
    """Draw a dashed line along a list of points (used for closed roads)."""
    carry, drawing = 0.0, True
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        pos = 0.0
        while pos < seg:
            step = min((on if drawing else off) - carry, seg - pos)
            if drawing:
                a, b = pos / seg, (pos + step) / seg
                draw.line([(x0 + (x1 - x0) * a, y0 + (y1 - y0) * a), (x0 + (x1 - x0) * b, y0 + (y1 - y0) * b)],
                          fill=fill, width=width)
            pos += step
            carry += step
            if carry >= (on if drawing else off) - 1e-6:
                carry, drawing = 0.0, not drawing
