"""
SOXL / SOXS 시뮬레이션 탭 (Tkinter)
메인 화면의 ttk.Notebook에 탭으로 추가되며, 실시간 시세는 update_prices()로 전달받습니다.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox

from sim_engine import SoxSimulator, SYMBOLS

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sim_state.json")


def _money(v):
    return f"${v:,.2f}"


def _signed_money(v):
    return f"{'+' if v >= 0 else '-'}${abs(v):,.2f}"


class SimulationTab(tk.Frame):

    def __init__(self, parent, theme, status_callback=None):
        super().__init__(parent, bg=theme["BG"])
        self.t = theme
        self.status_callback = status_callback
        self.sim = SoxSimulator(state_path=STATE_FILE)
        self.prices = {}

        self._build()
        self._refresh()

    # ========================================================
    # 화면 구성
    # ========================================================

    def _build(self):
        t = self.t

        # ---------- 설정 패널 ----------
        cfg = tk.Frame(self, bg=t["PANEL"], highlightbackground=t["BORDER"], highlightthickness=1)
        cfg.pack(fill="x", pady=(0, 10))

        tk.Label(
            cfg, text="  🧪 SOXL / SOXS 50:50 익절 시뮬레이션",
            font=("Arial", 13, "bold"), fg=t["TEXT"], bg=t["PANEL"], anchor="w",
        ).pack(fill="x", padx=10, pady=(12, 2))

        tk.Label(
            cfg,
            text="가상 자금을 SOXL·SOXS에 절반씩 매수 → 평균단가 대비 목표 수익률에 도달한 종목만 전량 매도 "
                 "(실시간 시세 기반 · 실제 주문 없음)",
            font=("Arial", 9), fg=t["MUTED"], bg=t["PANEL"], anchor="w",
        ).pack(fill="x", padx=12, pady=(0, 8))

        row = tk.Frame(cfg, bg=t["PANEL"])
        row.pack(fill="x", padx=12, pady=(0, 12))

        self.capital_var = tk.StringVar(value="1000")
        self.target_var = tk.StringVar(value="5")
        self.reinvest_var = tk.BooleanVar(value=True)

        tk.Label(row, text="초기 자금 ($)", fg=t["TEXT"], bg=t["PANEL"], font=("Arial", 10)).pack(side="left")
        self.capital_entry = tk.Entry(row, textvariable=self.capital_var, width=9, justify="right",
                                      font=("Arial", 10), relief="flat")
        self.capital_entry.pack(side="left", padx=(6, 18))

        tk.Label(row, text="목표 수익률 (%)", fg=t["TEXT"], bg=t["PANEL"], font=("Arial", 10)).pack(side="left")
        self.target_entry = tk.Entry(row, textvariable=self.target_var, width=5, justify="right",
                                     font=("Arial", 10), relief="flat")
        self.target_entry.pack(side="left", padx=(6, 18))

        self.reinvest_check = tk.Checkbutton(
            row, text="익절 후 같은 종목 재매수", variable=self.reinvest_var,
            fg=t["TEXT"], bg=t["PANEL"], selectcolor=t["DEEP_BG"],
            activebackground=t["PANEL"], activeforeground=t["TEXT"], font=("Arial", 10),
        )
        self.reinvest_check.pack(side="left", padx=(0, 18))

        self.start_btn = tk.Button(
            row, text="▶  시뮬레이션 시작", command=self._on_start,
            font=("Arial", 10, "bold"), fg=t["WHITE"], bg="#166534",
            activebackground="#15803d", activeforeground=t["WHITE"],
            relief="flat", bd=0, padx=16, pady=7, cursor="hand2",
        )
        self.start_btn.pack(side="left", padx=4)

        self.reset_btn = tk.Button(
            row, text="↺  초기화", command=self._on_reset,
            font=("Arial", 10, "bold"), fg=t["WHITE"], bg=t["PANEL_2"],
            activebackground=t["BORDER"], activeforeground=t["WHITE"],
            relief="flat", bd=0, padx=16, pady=7, cursor="hand2",
        )
        self.reset_btn.pack(side="left", padx=4)

        self.state_label = tk.Label(row, text="", fg=t["MUTED"], bg=t["PANEL"], font=("Arial", 9))
        self.state_label.pack(side="right")

        # ---------- 요약 카드 ----------
        cards = tk.Frame(self, bg=t["BG"])
        cards.pack(fill="x", pady=(0, 10))

        self.equity_value = self._card(cards, "총 자산")
        self.return_value = self._card(cards, "총 수익률")
        self.cash_value = self._card(cards, "현금")
        self.realized_value = self._card(cards, "실현 손익")

        # ---------- 보유 현황 ----------
        tk.Label(self, text="  보유 현황", font=("Arial", 12, "bold"),
                 fg=t["TEXT"], bg=t["BG"], anchor="w").pack(fill="x", pady=(2, 4))

        pos_cols = ("symbol", "shares", "avg", "price", "pnl", "target", "value")
        pos_heads = {
            "symbol": "종목", "shares": "수량", "avg": "평균단가", "price": "현재가",
            "pnl": "평가손익률", "target": "익절 목표가", "value": "평가금액",
        }
        self.pos_tree = self._tree(self, pos_cols, pos_heads, height=3)
        self.pos_tree.pack(fill="x")

        # ---------- 체결 내역 ----------
        tk.Label(self, text="  체결 내역 (최신순)", font=("Arial", 12, "bold"),
                 fg=t["TEXT"], bg=t["BG"], anchor="w").pack(fill="x", pady=(12, 4))

        trade_cols = ("time", "symbol", "side", "shares", "price", "pnl")
        trade_heads = {
            "time": "시간", "symbol": "종목", "side": "구분",
            "shares": "수량", "price": "체결가", "pnl": "실현손익",
        }
        wrap = tk.Frame(self, bg=t["BG"])
        wrap.pack(fill="both", expand=True)
        self.trade_tree = self._tree(wrap, trade_cols, trade_heads, height=10)
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.trade_tree.yview)
        self.trade_tree.configure(yscrollcommand=scroll.set)
        self.trade_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def _card(self, parent, title):
        t = self.t
        box = tk.Frame(parent, bg=t["DEEP_BG"], highlightbackground=t["BORDER"], highlightthickness=1)
        box.pack(side="left", fill="x", expand=True, padx=(0, 8))
        tk.Label(box, text=title, font=("Arial", 9), fg=t["MUTED"], bg=t["DEEP_BG"]).pack(pady=(10, 0))
        value = tk.Label(box, text="-", font=("Arial", 16, "bold"), fg=t["TEXT"], bg=t["DEEP_BG"])
        value.pack(pady=(2, 10))
        return value

    def _tree(self, parent, columns, heads, height):
        t = self.t
        tree = ttk.Treeview(parent, columns=columns, show="headings", height=height,
                            style="Modern.Treeview", selectmode="none")
        for col in columns:
            tree.heading(col, text=heads[col])
            tree.column(col, anchor="center", stretch=True, width=100)
        tree.tag_configure("up", foreground=t["RED"])      # 상승/이익 = 빨강
        tree.tag_configure("down", foreground=t["BLUE"])   # 하락/손실 = 파랑
        return tree

    # ========================================================
    # 버튼 동작
    # ========================================================

    def _on_start(self):
        try:
            capital = float(self.capital_var.get().replace(",", ""))
            target = float(self.target_var.get())
        except ValueError:
            messagebox.showwarning("입력 확인", "초기 자금과 목표 수익률에는 숫자를 입력하세요.")
            return

        try:
            events = self.sim.start(self.prices, capital, target, self.reinvest_var.get())
        except ValueError as e:
            messagebox.showinfo("시뮬레이션", str(e))
            return

        self._refresh()
        self._notify(events, prefix="시뮬레이션 시작")

    def _on_reset(self):
        if self.sim.started and not messagebox.askyesno(
            "초기화", "진행 중인 시뮬레이션과 체결 내역이 모두 삭제됩니다.\n초기화할까요?"
        ):
            return
        self.sim.reset()
        self._refresh()
        if self.status_callback:
            self.status_callback("시뮬레이션 초기화 완료")

    # ========================================================
    # 시세 수신 (메인 화면에서 호출)
    # ========================================================

    def update_prices(self, prices):
        """prices: {"SOXL": 52.3, "SOXS": 18.1, ...} - 필요한 종목만 사용합니다."""
        for sym in SYMBOLS:
            if sym in prices:
                self.prices[sym] = float(prices[sym])

        events = self.sim.on_prices(self.prices)
        self._refresh()
        if events:
            self._notify(events)

    def _notify(self, events, prefix=None):
        if not self.status_callback or not events:
            return
        last = events[-1]
        text = f"{last['symbol']} {last['side']} {last['shares']}주 @ ${last['price']:,.2f}"
        if last["pnl"] is not None:
            text += f"  (실현 {_signed_money(last['pnl'])})"
        self.status_callback(f"{prefix + '  •  ' if prefix else ''}{text}")

    # ========================================================
    # 화면 갱신
    # ========================================================

    def _refresh(self):
        t = self.t
        snap = self.sim.snapshot(self.prices)

        # 입력창 잠금/해제
        locked = "disabled" if snap["started"] else "normal"
        for w in (self.capital_entry, self.target_entry, self.reinvest_check, self.start_btn):
            w.config(state=locked)

        if snap["started"]:
            self.capital_var.set(f"{snap['initial_cash']:g}")
            self.target_var.set(f"{snap['take_profit_pct']:g}")
            self.reinvest_var.set(snap["reinvest"])
            self.state_label.config(
                text=f"진행 중  •  시작 {snap['started_at']}  •  목표 +{snap['take_profit_pct']:g}%",
                fg=t["TEXT"],
            )
        else:
            self.state_label.config(text="대기 중  •  시작 버튼을 눌러 현재가로 50:50 매수", fg=t["MUTED"])

        # 요약 카드
        self.equity_value.config(text=_money(snap["equity"]))
        self.cash_value.config(text=_money(snap["cash"]))

        ret = snap["return_pct"]
        self.return_value.config(
            text=f"{ret:+.2f}%" if snap["started"] else "-",
            fg=t["RED"] if ret > 0 else (t["BLUE"] if ret < 0 else t["TEXT"]),
        )
        rp = snap["realized_pnl"]
        self.realized_value.config(
            text=_signed_money(rp) if snap["started"] else "-",
            fg=t["RED"] if rp > 0 else (t["BLUE"] if rp < 0 else t["TEXT"]),
        )

        # 보유 현황
        for r in self.pos_tree.get_children():
            self.pos_tree.delete(r)
        for p in snap["positions"]:
            if not snap["started"]:
                self.pos_tree.insert("", "end", values=(p["symbol"], "-", "-",
                                     _money(p["price"]) if p["price"] else "-", "-", "-", "-"))
                continue
            held = p["shares"] > 0
            pnl = p["pnl_pct"]
            tag = ()
            if pnl is not None:
                tag = ("up",) if pnl > 0 else (("down",) if pnl < 0 else ())
            self.pos_tree.insert("", "end", tags=tag, values=(
                p["symbol"],
                f"{p['shares']:,}" if held else "0 (현금 대기)",
                _money(p["avg"]) if held else "-",
                _money(p["price"]) if p["price"] else "-",
                f"{pnl:+.2f}%" if pnl is not None else "-",
                _money(p["target_price"]) if held else "-",
                _money(p["value"]) if held else "-",
            ))

        # 체결 내역
        for r in self.trade_tree.get_children():
            self.trade_tree.delete(r)
        for tr in snap["trades"]:
            pnl = tr["pnl"]
            tag = ()
            if pnl is not None:
                tag = ("up",) if pnl > 0 else (("down",) if pnl < 0 else ())
            self.trade_tree.insert("", "end", tags=tag, values=(
                tr["time"], tr["symbol"],
                "매수" if tr["side"] == "BUY" else "매도",
                f"{tr['shares']:,}", _money(tr["price"]),
                _signed_money(pnl) if pnl is not None else "-",
            ))
