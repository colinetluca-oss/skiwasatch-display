"""Draws everything that sits on top of the 3D map: the resort panel on the
right, the resort pins, the peak names and the Home marker.

It's drawn with pygame onto one see-through picture the size of the screen,
which the renderer lays over the 3D view.
"""
import pygame

from . import config
from .data import level

C = config.COLORS
FONTS = config.ASSETS / "fonts"


class Fonts:
    """Loads each font size once and remembers it."""
    files = {"display": "BarlowCondensed-SemiBold.ttf", "display_bold": "BarlowCondensed-Bold.ttf",
             "body": "Inter-Regular.ttf", "body_bold": "Inter-SemiBold.ttf"}

    def __init__(self):
        self.cache = {}

    def __call__(self, kind, px):
        key = (kind, max(6, int(px)))
        if key not in self.cache:
            self.cache[key] = pygame.font.Font(str(FONTS / self.files[kind]), key[1])
        return self.cache[key]


def text(surf, font, s, color, pos, anchor="topleft", spacing=0.0):
    """Draw text. `anchor` says which corner `pos` is, e.g. "topright". `spacing` adds letter spacing."""
    if spacing:
        glyphs = [font.render(ch, True, color) for ch in s]
        w = sum(g.get_width() for g in glyphs) + spacing * (len(s) - 1)
        img = pygame.Surface((max(1, int(w)), font.get_height()), pygame.SRCALPHA)
        x = 0.0
        for g in glyphs:
            img.blit(g, (int(x), 0)); x += g.get_width() + spacing
    else:
        img = font.render(s, True, color)
    rect = img.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
    surf.blit(img, rect)
    return rect


def rrect(surf, color, rect, radius, alpha=255, width=0):
    if alpha < 255:
        tmp = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
        pygame.draw.rect(tmp, (*color, alpha), (0, 0, rect[2], rect[3]), width, border_radius=int(radius))
        surf.blit(tmp, rect[:2])
    else:
        pygame.draw.rect(surf, color, rect, width, border_radius=int(radius))


def wrap(font, s, width):
    words, lines, cur = s.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if font.size(t)[0] <= width or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


class Overlay:
    def __init__(self, width, height):
        self.w, self.h = width, height
        self.f = Fonts()
        self.u = width / 100          # 1% of the screen width: every size below is a multiple of this
        self.map_w = round(width * config.MAP_SHARE)

    # ---------------------------------------------------------------- panel
    def panel(self, s, d, direction):
        u, x0, W, H = self.u, self.map_w, self.w, self.h
        pygame.draw.rect(s, C["panel"], (x0, 0, W - x0, H))
        pygame.draw.line(s, C["line"], (x0, 0), (x0, H))
        L, R = x0 + 1.6 * u, W - 1.6 * u
        y = 1.5 * u

        # header
        r = text(s, self.f("display_bold", 2.3 * u), "WASATCH", C["ink"], (L, y - .25 * u), spacing=.14 * 2.3 * u)
        text(s, self.f("body", 1.0 * u), d.when, C["muted"], (L, r.bottom + .25 * u))
        if d.is_sample:
            cf = self.f("display", .85 * u)
            lab = "SAMPLE DATA"
            tw = cf.size(lab)[0] + .12 * .85 * u * (len(lab) - 1)
            box = pygame.Rect(0, 0, int(tw + 1.4 * u), int(cf.get_height() + .3 * u)); box.topright = (int(R), int(y))
            pygame.draw.rect(s, C["warn"], box, 1, border_radius=box.height // 2)
            text(s, cf, lab, C["warn"], box.center, "center", spacing=.12 * .85 * u)
        y = r.bottom + 2.6 * u

        # column headings
        snow_w, drive_w, gap = 6 * u, 7.4 * u, .6 * u
        drive_r = R - .5 * u
        snow_r = drive_r - drive_w - gap
        hf = self.f("body", .75 * u)
        sp = .1 * .75 * u
        text(s, hf, "RESORT", C["muted"], (L + 1.05 * u, y), spacing=sp)
        text(s, hf, "NEW SNOW", C["muted"], (snow_r, y), "topright", spacing=sp)
        text(s, hf, "DRIVE THERE" if direction == "to" else "DRIVE HOME", C["muted"], (drive_r + .5 * u, y), "topright", spacing=sp)
        y += hf.get_height() + .4 * u
        pygame.draw.line(s, C["line"], (L, y), (R, y))
        y += 1.0 * u

        # bottom-up: footer, then alerts, so the rows can fill what's left
        ff = self.f("body", .72 * u)
        foot_y = H - 1.5 * u - ff.get_height()
        pygame.draw.line(s, C["line"], (L, foot_y - .6 * u), (R, foot_y - .6 * u))
        lx = L
        for key, lab in (("good", "Normal"), ("warn", "Slow"), ("bad", "Heavy or closed")):
            pygame.draw.rect(s, C[key], (lx, foot_y + ff.get_height() / 2 - .15 * u, 1.2 * u, .3 * u), border_radius=2)
            r = text(s, ff, lab, C["muted"], (lx + 1.5 * u, foot_y)); lx = r.right + .8 * u
        text(s, ff, "Updated 2 min ago" if d.is_sample else "Live", C["muted"], (R, foot_y), "topright")

        af, ab = self.f("body", .85 * u), self.f("body_bold", .85 * u)
        alert_lines = []
        for lv, bold, rest in d.alerts:
            lines = wrap(af, (bold + " " + rest).strip(), R - L - .95 * u)
            alert_lines.append((lv, bold, lines))
        line_h = af.get_linesize() * 1.05
        alerts_h = sum(len(l) * line_h for _, _, l in alert_lines) + .4 * u * max(0, len(alert_lines) - 1)
        ay = foot_y - 1.6 * u - alerts_h
        for lv, bold, lines in alert_lines:
            col = C["good"] if lv == "good" else C[lv]
            pygame.draw.rect(s, col, (L, ay, .35 * u, len(lines) * line_h), border_radius=2)
            for i, ln in enumerate(lines):
                tx = L + .95 * u
                if i == 0 and bold and ln.startswith(bold):
                    r = text(s, ab, bold, C["ink"], (tx, ay)); tx = r.right + af.size(" ")[0]; ln = ln[len(bold):].strip()
                text(s, af, ln, C["ink"], (tx, ay))
                ay += line_h
            ay += .4 * u

        # resort rows, deepest new snow first
        rows_bottom = foot_y - 1.6 * u - alerts_h - 1.0 * u
        resorts = sorted(config.RESORTS, key=lambda r: -d.snow[r["id"]][0])
        n, rgap = len(resorts), .45 * u
        rh = (rows_bottom - y - rgap * (n - 1)) / n
        nf, sf = self.f("display", 1.75 * u), self.f("body", .78 * u)
        bf, df, mf = self.f("display_bold", 3.1 * u), self.f("display_bold", 2.3 * u), self.f("body", .72 * u)
        for r in resorts:
            n24, n48, base = d.snow[r["id"]]
            mins = d.times[direction][r["id"]]
            lv = level(mins, r["normal"])
            box = pygame.Rect(int(L), int(y), int(R - L), int(rh))
            if lv in ("bad", "closed"):
                rrect(s, C["bad"], box, .4 * u, alpha=18)
            pygame.draw.rect(s, C["good" if lv == "good" else "warn" if lv == "warn" else "bad"],
                             (box.x, box.y, max(2, int(.35 * u)), box.h), border_radius=2)
            cy = box.centery
            nh = nf.get_height() * .82
            sub = (f"+{n48}″ next 48h · " if n48 else "") + f"base {base}″"
            text(s, nf, r["name"], C["ink"], (L + 1.0 * u, cy - nh / 2 - .1 * u), "midleft")
            text(s, sf, sub, C["muted"], (L + 1.0 * u, cy + nh / 2 - .1 * u), "midleft")
            text(s, bf, f"{n24}″", C["snow"] if n24 else tuple(int(v * .6) for v in C["muted"]),
                 (snow_r, cy), "midright")
            dcol = C["good" if lv == "good" else "warn" if lv == "warn" else "bad"]
            text(s, df, "Closed" if mins is None else f"{mins} min", dcol, (drive_r, cy - .35 * u), "midright")
            text(s, mf, "road closed" if mins is None else f"normally {r['normal']}", C["muted"],
                 (drive_r, cy + 1.25 * u), "midright")
            y += rh + rgap

    # ---------------------------------------------------------------- pins
    def pins(self, s, d, spots):
        """`spots` says where peaks and places land on screen (see Terrain.spots)."""
        u, mw, H = self.u, self.map_w, self.h
        # peak names
        pf = self.f("body", .72 * u); pb = self.f("body_bold", .72 * u)
        for p in spots["peaks"]:
            x, yy, ok = p["x"], p["y"], p["visible"]
            if not ok:
                continue
            col = (201, 213, 226)
            pygame.draw.polygon(s, col, [(x - 4, yy - 7), (x + 4, yy - 7), (x, yy - 2)])
            for dx, dy in ((1, 1), (0, 0)):
                c = (0, 0, 0) if dx else col
                text(s, pf, f"{p['ft']:,} ft", c, (x + dx, yy - 9 + dy), "midbottom")
                text(s, pb, p["name"], c, (x + dx, yy - 9 - pf.get_linesize() + dy), "midbottom")

        # resort pins + home
        items = [("home", config.HOME_NAME, None, 26)] + [(r["id"], r["name"], d.snow[r["id"]][0], st)
                                                          for r, st in zip(config.RESORTS, (96, 34, 84, 30, 40))]
        xy = [(spots["places"][k]["x"], spots["places"][k]["y"]) for k, *_ in items]
        vis = [spots["places"][k]["visible"] for k, *_ in items]
        nf = self.f("display", 1.35 * u); hf = self.f("display", 1.15 * u)
        sf = self.f("display_bold", 1.9 * u)
        placed = []
        order = sorted(range(len(items)), key=lambda i: -xy[i][1])   # nearest (lowest on screen) first
        for i in order:
            if not vis[i]:
                continue
            key, name, snow, stick = items[i]
            x, yy = xy[i]
            f = hf if key == "home" else nf
            tw = max(f.size(name)[0], sf.size(f"{snow}″")[0] if snow is not None else 0) + 1.6 * u
            th = f.get_height() * .9 + (sf.get_height() * .85 if snow is not None else 0) + .5 * u
            max_stick = max(stick, yy - th - 10)

            def box_for(st):
                return pygame.Rect(int(x - tw / 2), int(yy - st - th), int(tw), int(th))
            b = box_for(stick)
            while any(b.inflate(8, 8).colliderect(q) for q in placed) and stick + 6 <= max_stick:
                stick += 6; b = box_for(stick)
            shift = max(0, 8 - b.left) - max(0, b.right - (mw - 8))
            b.x += shift
            placed.append(b)
            # halo ring grows with new snow
            if snow:
                r = int(6 + snow ** .5 * 3.2)
                ring = pygame.Surface((2 * r + 2, 2 * r + 2), pygame.SRCALPHA)
                pygame.draw.circle(ring, (*C["snow"], 46), (r + 1, r + 1), r)
                s.blit(ring, (x - r - 1, yy - r - 1))
            # stick, foot, tag
            for k in range(int(stick)):
                a = int(255 - 180 * k / max(1, stick))
                s.fill((*C["snow"], a), (int(x) - 1, int(yy - k), 2, 1))
            if key == "home":
                pygame.draw.rect(s, (5, 8, 12), (x - 7, yy - 7, 14, 14), border_radius=3)
                pygame.draw.rect(s, C["ink"], (x - 4, yy - 4, 8, 8), border_radius=2)
            else:
                pygame.draw.circle(s, (5, 8, 12), (int(x), int(yy)), 7)
                pygame.draw.circle(s, C["ink"], (int(x), int(yy)), 4)
            rrect(s, (9, 14, 22), b, 8, alpha=205)
            rrect(s, C["snow"], b, 8, alpha=70, width=1)
            ty = b.y + .2 * u
            text(s, f, name, C["ink"], (b.centerx, ty), "midtop")
            if snow is not None:
                text(s, sf, f"{snow}″", C["snow"] if snow else C["muted"], (b.centerx, ty + f.get_height() * .85), "midtop")

    def draw_surface(self, d, direction, spots):
        s = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self.pins(s, d, spots)
        self.panel(s, d, direction)
        return s

    def draw(self, d, direction, spots):
        return pygame.image.tobytes(self.draw_surface(d, direction, spots), "RGBA")
