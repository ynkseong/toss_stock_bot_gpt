"""
AMS 마스코트 - 빨강/파랑 더듬이를 가진 귀여운 개미 (Tkinter Canvas로 직접 그림)

  • 빨간 더듬이 = 상승, 파란 더듬이 = 하락 (한국식 색상)
  • 가만히 있어도 더듬이를 살랑살랑, 몸을 통통, 다리는 총총, 눈은 깜빡
  • 개미를 클릭하면 폴짝 뛰면서 한마디 합니다
  • 가끔 혼자서도 중얼거리고, say()로 다른 곳(예: 익절 체결)에서 말을 시킬 수도 있습니다
"""

import math
import random
import time
import tkinter as tk
import tkinter.font as tkfont

QUIPS = [
    "빨강은 오르고, 파랑은 내려~",
    "5% 먹고 튀자!",
    "오늘도 열심히 줍줍!",
    "존버는 승리한다...?",
    "수수료 $1이 아깝다...",
    "개미는 오늘도 출근 중",
    "물렸다면... 기다려 보자",
    "손절은 짧게, 익절은 칼같이!",
    "3배 레버리지는 맵다 맵아",
    "간식 주세요 (설탕 말고 수익)",
    "더듬이가 움찔했어!",
]

BODY = "#f59e0b"        # 몸통 (앰버)
BODY_EDGE = "#b45309"
BODY_LIGHT = "#fcd34d"
RED = "#ef4444"         # 상승
BLUE = "#3b82f6"        # 하락


class AntMascot(tk.Canvas):

    def __init__(self, parent, bg="#0f172a", width=330, height=86, **kw):
        super().__init__(parent, width=width, height=height, bg=bg,
                         highlightthickness=0, bd=0, cursor="hand2", **kw)
        self._bg = bg
        self._t0 = time.monotonic()
        self._font = tkfont.Font(family="Malgun Gothic", size=9, weight="bold")
        self._shadow = "#1e293b"

        now = self._now()
        self._next_blink = now + random.uniform(2.0, 4.0)
        self._blink_until = 0.0
        self._hop_start = 0.0
        self._hop_until = 0.0
        self._bubble_text = ""
        self._bubble_until = 0.0
        self._next_idle = now + random.uniform(40, 70)
        self._last_quip = None
        self._job = None

        self.bind("<Button-1>", self._on_click)
        self.bind("<Destroy>", self._on_destroy)
        self._tick()

    # --------------------------------------------------------
    # 외부에서 쓰는 기능
    # --------------------------------------------------------

    def say(self, text, seconds=2.6, hop=True):
        now = self._now()
        self._bubble_text = text
        self._bubble_until = now + seconds
        if hop:
            self._hop_start = now
            self._hop_until = now + 0.55

    # --------------------------------------------------------
    # 내부 동작
    # --------------------------------------------------------

    def _now(self):
        return time.monotonic() - self._t0

    def _on_click(self, _event):
        choices = [q for q in QUIPS if q != self._last_quip]
        self._last_quip = random.choice(choices)
        self.say(self._last_quip)

    def _on_destroy(self, _event):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    def _tick(self):
        if not self.winfo_exists():
            return
        t = self._now()

        # 혼자 중얼거리기 (아주 가끔)
        if t >= self._next_idle:
            self._next_idle = t + random.uniform(45, 80)
            if t >= self._bubble_until:
                self._on_click(None)

        # 눈 깜빡
        if t >= self._next_blink:
            self._blink_until = t + 0.15
            self._next_blink = t + random.uniform(2.5, 5.0)

        self._draw(t)
        self._job = self.after(50, self._tick)  # 약 20fps

    # --------------------------------------------------------
    # 그리기
    # --------------------------------------------------------

    def _oval(self, cx, cy, rx, ry, **kw):
        return self.create_oval(cx - rx, cy - ry, cx + rx, cy + ry, tags="ant", **kw)

    def _antenna(self, base, angle_deg, color, t, phase, speed):
        x, y = base
        wiggle = math.sin(t * speed + phase) * 24
        th1 = math.radians(angle_deg + wiggle)
        x1, y1 = x + math.cos(th1) * 15, y - math.sin(th1) * 15
        curve = -26 if angle_deg < 90 else 26
        th2 = math.radians(angle_deg + wiggle * 1.6 + curve)
        x2, y2 = x1 + math.cos(th2) * 13, y1 - math.sin(th2) * 13
        self.create_line(x, y, x1, y1, x2, y2, smooth=True, width=3, fill=color,
                         capstyle="round", joinstyle="round", tags="ant")
        self._oval(x2, y2, 4.2, 4.2, fill=color, outline="")

    def _draw(self, t):
        self.delete("ant")

        # 통통 튀는 몸 + 클릭 시 폴짝
        bob = math.sin(t * 3.2) * 1.8
        hop = 0.0
        if t < self._hop_until:
            p = (t - self._hop_start) / 0.55
            hop = -math.sin(math.pi * min(max(p, 0), 1)) * 16
        by = bob + hop

        ground = 76
        # 그림자 (뛰어오르면 작아짐)
        sh = max(0.45, 1 + hop / 40)
        self._oval(54, ground + 2, 36 * sh, 4 * sh, fill=self._shadow, outline="")

        # 다리 (총총 걸음)
        for i, x in enumerate((45, 55, 65)):
            ph = math.pi if i == 1 else 0.0
            sw = math.sin(t * 7 + ph) * 4.5
            lift = max(0.0, math.cos(t * 7 + ph)) * 2.5
            foot = (x + sw - 4, ground - lift + (hop * 0.4 if hop else 0))
            knee = (x + sw * 0.4 - 6, 66 + by * 0.5)
            self.create_line(x, 58 + by, knee[0], knee[1], foot[0], foot[1],
                             width=2.5, fill=BODY_EDGE, capstyle="round", joinstyle="round", tags="ant")

        # 몸통: 배 - 가슴 - 머리
        self._oval(28, 52 + by, 20, 15, fill=BODY, outline=BODY_EDGE, width=2)
        self._oval(22, 46 + by, 7, 4, fill=BODY_LIGHT, outline="")
        self._oval(56, 51 + by, 12, 10, fill=BODY, outline=BODY_EDGE, width=2)
        hx, hy = 84, 42 + by
        self._oval(hx, hy, 18, 17, fill=BODY, outline=BODY_EDGE, width=2)
        self._oval(hx - 6, hy - 10, 6, 3.5, fill=BODY_LIGHT, outline="")

        # 더듬이: 빨강(오른쪽) / 파랑(왼쪽) 하나씩
        self._antenna((hx + 6, hy - 15), 62, RED, t, 0.0, 4.3)
        self._antenna((hx - 6, hy - 15), 118, BLUE, t, 1.7, 3.7)

        # 눈 (깜빡)
        blinking = t < self._blink_until
        for ex in (hx - 7, hx + 7):
            ey = hy - 3
            if blinking:
                self.create_line(ex - 5, ey, ex + 5, ey, width=2.5, fill="#111827",
                                 capstyle="round", tags="ant")
            else:
                self._oval(ex, ey, 5.6, 6.2, fill="#ffffff", outline="#111827", width=1.5)
                self._oval(ex + 1.6, ey + 0.8, 2.8, 3.2, fill="#111827", outline="")
                self._oval(ex + 2.6, ey - 0.6, 1.0, 1.0, fill="#ffffff", outline="")

        # 볼터치 + 웃는 입
        self._oval(hx - 13, hy + 7, 3.6, 2.4, fill="#fb7185", outline="")
        self._oval(hx + 13, hy + 7, 3.6, 2.4, fill="#fb7185", outline="")
        self.create_arc(hx - 7, hy + 2, hx + 7, hy + 14, start=205, extent=130,
                        style="arc", outline="#7c2d12", width=2, tags="ant")

        # 말풍선
        if t < self._bubble_until and self._bubble_text:
            self._draw_bubble(self._bubble_text)

    def _draw_bubble(self, text):
        x0, y0 = 116, 14
        w = self._font.measure(text) + 24
        h = 30
        x1, y1 = x0 + w, y0 + h
        r = 9
        pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
               x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
        self.create_polygon(pts, smooth=True, fill="#f8fafc", outline="#94a3b8", tags="ant")
        # 꼬리 (개미 머리 쪽)
        self.create_polygon(x0 + 1, y0 + 10, x0 + 1, y0 + 22, x0 - 9, y0 + 20,
                            fill="#f8fafc", outline="#94a3b8", tags="ant")
        self.create_line(x0 + 1.5, y0 + 11, x0 + 1.5, y0 + 21, fill="#f8fafc", width=2, tags="ant")
        self.create_text(x0 + w / 2, y0 + h / 2, text=text, fill="#0f172a",
                         font=self._font, tags="ant")
