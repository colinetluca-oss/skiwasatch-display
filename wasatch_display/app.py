"""Starts the display.

Run it with:   python -m wasatch_display            (full screen)
               python -m wasatch_display --windowed (in a window, for testing on a laptop)
               python -m wasatch_display --screenshot out.png  (draw one picture and quit)

Two ways to draw the map:
  light (default)  uses the pre-rendered pictures in assets/prerendered. No 3D
                   work at all, so it runs on a cheap Pi (Pi 4 or Pi 5, 2 GB).
  --3d             draws the mountains live with OpenGL. Needs a Pi 5 and lets
                   you change the camera without re-running the pre-render.

Keys while it runs: 1-4 switch sample situations, D flips direction, Esc quits.
"""
import argparse
import datetime
import time

import numpy as np
import pygame

from . import data, light
from .overlay import Overlay


def auto_direction(now=None):
    """Mornings show drives to the resorts; from noon on, drives back home."""
    now = now or datetime.datetime.now()
    return "to" if now.hour < 12 else "from"


class LightDisplay:
    """Map from pre-rendered pictures; everything drawn with plain pygame."""
    def __init__(self, w, h):
        self.overlay = Overlay(w, h)
        self.map = light.LightMap(self.overlay.map_w, h)

    def draw(self, target, d, direction):
        rgb = self.map.compose(d.roads[direction])
        target.fill((11, 17, 26))
        target.blit(pygame.surfarray.make_surface(np.ascontiguousarray(rgb.swapaxes(0, 1))), (0, 0))
        target.blit(self.overlay.draw_surface(d, direction, self.map.spots), (0, 0))


class GLDisplay:
    """Map drawn live in 3D with OpenGL."""
    def __init__(self, ctx, w, h):
        from .terrain import Terrain
        self.ctx, self.w, self.h = ctx, w, h
        self.overlay = Overlay(w, h)
        self.terrain = Terrain(ctx)

    def draw(self, fbo, d, direction):
        t = self.terrain
        t.paint_roads(d.roads[direction])
        proj, view = t.camera(self.overlay.map_w, self.h)
        spots = t.spots(proj, view, self.overlay.map_w, self.h)
        t.render(fbo, self.overlay.map_w, self.h, self.overlay.draw(d, direction, spots), self.w)


def main():
    ap = argparse.ArgumentParser(description="Wasatch snow and traffic wall display")
    ap.add_argument("--windowed", action="store_true", help="run in a window instead of full screen")
    ap.add_argument("--size", default="1920x1080", help="window or screenshot size, e.g. 1920x1080")
    ap.add_argument("--demo", default="powder", choices=data.SAMPLE_ORDER, help="which sample situation to show")
    ap.add_argument("--direction", choices=["to", "from", "auto"], default="auto")
    ap.add_argument("--3d", dest="live3d", action="store_true", help="draw the mountains live with OpenGL")
    ap.add_argument("--screenshot", metavar="FILE", help="draw one frame to a PNG file and exit")
    args = ap.parse_args()
    w, h = map(int, args.size.lower().split("x"))
    use_gl = args.live3d or not light.available()
    if not args.live3d and use_gl:
        print("No pre-rendered map found; drawing in 3D. Run: python -m wasatch_display.prerender")

    pygame.init()
    scenario = args.demo
    direction = auto_direction() if args.direction == "auto" else args.direction
    if args.demo == "exodus" and args.direction == "auto":
        direction = "from"

    if args.screenshot:
        if use_gl:
            import moderngl
            from PIL import Image
            ctx = moderngl.create_standalone_context(require=310)
            fbo = ctx.simple_framebuffer((w, h))
            GLDisplay(ctx, w, h).draw(fbo, data.sample(scenario), direction)
            Image.frombytes("RGB", (w, h), fbo.read(components=3)).transpose(Image.FLIP_TOP_BOTTOM).save(args.screenshot)
        else:
            surf = pygame.Surface((w, h))
            LightDisplay(w, h).draw(surf, data.sample(scenario), direction)
            pygame.image.save(surf, args.screenshot)
        print("saved", args.screenshot)
        return

    flags = pygame.FULLSCREEN if not args.windowed else 0
    size = (w, h) if args.windowed else (0, 0)
    if use_gl:
        import moderngl
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 1)
        screen = pygame.display.set_mode(size, flags | pygame.OPENGL | pygame.DOUBLEBUF)
    else:
        screen = pygame.display.set_mode(size, flags)
    w, h = pygame.display.get_surface().get_size()
    if not args.windowed:
        pygame.mouse.set_visible(False)
    pygame.display.set_caption("Wasatch")
    if use_gl:
        ctx = moderngl.create_context(require=310)
        display = GLDisplay(ctx, w, h)
        draw = lambda d, dr: display.draw(ctx.screen, d, dr)
    else:
        display = LightDisplay(w, h)
        draw = lambda d, dr: display.draw(screen, d, dr)

    dirty, last_minute = True, None
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                pygame.quit(); return
            if ev.type == pygame.KEYDOWN:
                if pygame.K_1 <= ev.key <= pygame.K_4:
                    scenario = data.SAMPLE_ORDER[ev.key - pygame.K_1]; dirty = True
                elif ev.key == pygame.K_d:
                    direction = "from" if direction == "to" else "to"; dirty = True
        minute = time.strftime("%H:%M")
        if minute != last_minute:            # once a minute, re-check the direction
            last_minute = minute
            if args.direction == "auto":
                nd = auto_direction()
                dirty = dirty or nd != direction
                direction = nd
        if dirty:
            draw(data.sample(scenario), direction)
            pygame.display.flip()
            dirty = False
        time.sleep(0.1)   # nothing moves, so there's no need to redraw 60 times a second


if __name__ == "__main__":
    main()
