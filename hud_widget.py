from __future__ import annotations

import math
import random
from pathlib import Path

from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.graphics import (
    Color, Ellipse, Line, Point, PopMatrix, PushMatrix, Rectangle,
    Rotate, StencilPop, StencilPush, Scale, Translate,
)
from kivy.graphics.instructions import InstructionGroup
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex


class C:
    BG       = "#00060a"
    PRI      = "#00d4ff"
    PRI_DIM  = "#007a99"
    PRI_GHO  = "#001f2e"
    ACC      = "#ff6b00"
    ACC2     = "#ffcc00"
    GREEN    = "#00ff88"
    MUTED_C  = "#ff3366"
    TEXT     = "#8ffcff"
    TEXT_DIM = "#3a8a9a"


def qcol(h: str, a: float = 1.0):
    r, g, b = get_color_from_hex(h)[:3]
    return (r, g, b, a)


class HudWidget(Widget):
    def __init__(self, face_path: str = "", **kwargs):
        super().__init__(**kwargs)
        self.muted    = False
        self.speaking = False
        self.state    = "INITIALISING"

        self._tick       = 0
        self._scale      = 1.0
        self._tgt_scale  = 1.0
        self._halo       = 55.0
        self._tgt_halo   = 55.0
        self._last_t     = 0.0
        self._scan       = 0.0
        self._scan2      = 180.0
        self._rings      = [0.0, 120.0, 240.0]
        self._pulses     = [0.0, 50.0, 100.0]
        self._blink      = True
        self._blink_tick = 0
        self._particles  = []

        self._face_texture = None
        if face_path and Path(face_path).exists():
            try:
                self._face_texture = CoreImage(face_path).texture
            except Exception:
                self._face_texture = None

        Clock.schedule_interval(self._step, 1 / 60)

    def _step(self, dt):
        import time
        self._tick += 1
        now = time.time()
        if now - self._last_t > (0.12 if self.speaking else 0.5):
            if self.speaking:
                self._tgt_scale = random.uniform(1.06, 1.14)
                self._tgt_halo  = random.uniform(145, 190)
            elif self.muted:
                self._tgt_scale = random.uniform(0.998, 1.002)
                self._tgt_halo  = random.uniform(15, 28)
            else:
                self._tgt_scale = random.uniform(1.001, 1.008)
                self._tgt_halo  = random.uniform(48, 68)
            self._last_t = now

        sp = 0.38 if self.speaking else 0.15
        self._scale += (self._tgt_scale - self._scale) * sp
        self._halo  += (self._tgt_halo  - self._halo)  * sp

        speeds = [1.3, -0.9, 2.0] if self.speaking else [0.55, -0.35, 0.9]
        for i, spd in enumerate(speeds):
            self._rings[i] = (self._rings[i] + spd) % 360

        self._scan  = (self._scan  + (3.0 if self.speaking else 1.3)) % 360
        self._scan2 = (self._scan2 + (-2.0 if self.speaking else -0.75)) % 360

        fw  = min(self.width, self.height)
        lim = fw * 0.74
        spd = 4.2 if self.speaking else 2.0
        self._pulses = [r + spd for r in self._pulses if r + spd < lim]
        if len(self._pulses) < 3 and random.random() < (0.07 if self.speaking else 0.025):
            self._pulses.append(0.0)

        if self.speaking and random.random() < 0.28:
            cx, cy = self.width / 2, self.height / 2
            ang = random.uniform(0, 2 * math.pi)
            r_s = fw * 0.28
            self._particles.append([
                cx + math.cos(ang) * r_s, cy + math.sin(ang) * r_s,
                math.cos(ang) * random.uniform(0.9, 2.4),
                math.sin(ang) * random.uniform(0.9, 2.4) - 0.4, 1.0,
            ])
        self._particles = [
            [p[0]+p[2], p[1]+p[3], p[2]*0.97, p[3]*0.97, p[4]-0.028]
            for p in self._particles if p[4] > 0
        ]

        self._blink_tick += 1
        if self._blink_tick >= 38:
            self._blink = not self._blink
            self._blink_tick = 0
        self.canvas.ask_update()

    def _draw_halo(self, cx, cy, fw):
        r_face = fw * 0.31
        for i in range(10):
            r   = r_face * (1.8 - i * 0.08)
            frc = 1.0 - i / 10
            a   = max(0, min(1.0, self._halo * 0.085 / 255 * frc))
            col = C.MUTED_C if self.muted else C.PRI
            Color(*qcol(col, a))
            Line(circle=(cx, cy, r), width=1.5)

    def _draw_pulses(self, cx, cy, fw):
        for pr in self._pulses:
            a = max(0, 230 / 255 * (1.0 - pr / (fw * 0.74)))
            col = C.MUTED_C if self.muted else C.PRI
            Color(*qcol(col, a))
            Line(circle=(cx, cy, pr), width=1.5)

    def _draw_rings(self, cx, cy, fw):
        for idx, (r_frac, w_r, arc_l, gap) in enumerate(
            [(0.48, 3, 115, 78), (0.40, 2, 78, 55), (0.32, 1, 56, 40)]
        ):
            ring_r = fw * r_frac
            base   = self._rings[idx]
            a_val  = max(0, min(1.0, self._halo / 255 * (1.0 - idx * 0.18)))
            col    = C.MUTED_C if self.muted else C.PRI
            Color(*qcol(col, a_val))
            angle = base
            while angle < base + 360:
                Line(circle=(cx, cy, ring_r, math.radians(angle), math.radians(arc_l)), width=w_r)
                angle += arc_l + gap

    def _draw_scanners(self, cx, cy, fw):
        sr = fw * 0.50
        sa = min(1.0, self._halo * 1.5 / 255)
        ex = 75 if self.speaking else 44
        col = C.MUTED_C if self.muted else C.PRI
        Color(*qcol(col, sa))
        Line(circle=(cx, cy, sr, math.radians(self._scan), math.radians(ex)), width=2.5)
        Color(*qcol(C.ACC, sa / 2))
        Line(circle=(cx, cy, sr, math.radians(self._scan2), math.radians(ex)), width=1.5)

    def _draw_ticks(self, cx, cy, fw):
        t_out, t_in = fw * 0.497, fw * 0.474
        Color(*qcol(C.PRI, 140 / 255))
        for deg in range(0, 360, 10):
            rad = math.radians(deg)
            inn = t_in if deg % 30 == 0 else t_in + 6
            Line(points=[
                cx + t_out * math.cos(rad), cy - t_out * math.sin(rad),
                cx + inn  * math.cos(rad), cy - inn  * math.sin(rad),
            ], width=1)

    def _draw_crosshair(self, cx, cy, fw):
        ch_r, gap_h = fw * 0.51, fw * 0.16
        Color(*qcol(C.PRI, self._halo * 0.5 / 255))
        Line(points=[cx - ch_r, cy, cx - gap_h, cy])
        Line(points=[cx + gap_h, cy, cx + ch_r, cy])
        Line(points=[cx, cy - ch_r, cx, cy - gap_h])
        Line(points=[cx, cy + gap_h, cx, cy + ch_r])

    def _draw_corners(self, cx, cy, fw):
        bl = 24
        Color(*qcol(C.PRI, 210 / 255))
        hl, hr = cx - fw // 2, cx + fw // 2
        ht, hb = cy - fw // 2, cy + fw // 2
        for bx, by, dx, dy in [(hl,ht,1,1),(hr,ht,-1,1),(hl,hb,1,-1),(hr,hb,-1,-1)]:
            Line(points=[bx, by, bx + dx * bl, by])
            Line(points=[bx, by, bx, by + dy * bl])

    def _draw_face(self, cx, cy, fw):
        if self._face_texture:
            fsz = int(fw * 0.62 * self._scale)
            PushMatrix()
            Translate(cx - fsz / 2, cy - fsz / 2)
            StencilPush()
            Color(1, 1, 1, 1)
            Ellipse(pos=(0, 0), size=(fsz, fsz))
            StencilPop()
            Color(1, 1, 1, 1)
            Rectangle(texture=self._face_texture, pos=(0, 0), size=(fsz, fsz))
            StencilPop()
            PopMatrix()
        else:
            orb_r = int(fw * 0.27 * self._scale)
            oc = (200, 0, 50) if self.muted else (0, 60, 110)
            for i in range(8, 0, -1):
                r2  = int(orb_r * i / 8)
                frc = i / 8
                a   = max(0, min(1.0, self._halo * 1.1 / 255 * frc))
                Color(oc[0] * frc / 255, oc[1] * frc / 255, oc[2] * frc / 255, a)
                Ellipse(pos=(cx - r2, cy - r2), size=(r2 * 2, r2 * 2))

    def _draw_particles(self):
        for pt in self._particles:
            a = max(0, min(1.0, pt[4]))
            Color(*qcol(C.PRI, a))
            Ellipse(pos=(pt[0] - 2.5, pt[1] - 2.5), size=(5, 5))

    def _draw_grid(self):
        Color(*qcol(C.PRI_GHO, 1))
        W, H = self.width, self.height
        for x in range(0, int(W), 48):
            for y in range(0, int(H), 48):
                Point(points=[x, y])

    def draw_hud(self, cx, cy, fw):
        self._draw_grid()
        self._draw_halo(cx, cy, fw)
        self._draw_pulses(cx, cy, fw)
        self._draw_rings(cx, cy, fw)
        self._draw_scanners(cx, cy, fw)
        self._draw_ticks(cx, cy, fw)
        self._draw_crosshair(cx, cy, fw)
        self._draw_corners(cx, cy, fw)
        self._draw_face(cx, cy, fw)
        self._draw_particles()
