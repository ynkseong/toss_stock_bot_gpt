import tkinter as tk
from tkinter import ttk
import threading
import time
from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo
from collections import defaultdict, deque

from token_manager import get_access_token
from toss_api import get_stock_prices, parse_stock_data, STOCKS
from market_indicators import get_market_indicators
from data_manager import DataManager
from news_collector import collect_news
# ============================================================
# 색상 테마
# ============================================================

BG = "#0f172a"
PANEL = "#0f2f2a"     # 네이비-그린 블렌드 (기존 슬레이트에서 변경)
PANEL_2 = "#163a33"   # PANEL보다 한 톤 밝은 네이비-그린
BORDER = "#2f4a44"    # 네이비-그린 톤에 맞춘 보더
TEXT = "#e5e7eb"
MUTED = "#94a3b8"
RED = "#ef4444"       # 상승
BLUE = "#3b82f6"      # 하락
BLACK = "#111827"     # 0%
WHITE = "#ffffff"
STOCK_BG = "#f8fafc"
STOCK_TEXT = "#111827"

DEEP_BG = "#08221c"        # 차트/판단 박스 등 짙은 강조 영역
STATUS_BAR_BG = "#03150f"  # 하단 상태바 (그라데이션 최하단 톤과 맞춤)

GRADIENT_TOP = "#0f172a"     # slate-900 (네이비)
GRADIENT_BOTTOM = "#064e3b"  # emerald-900 (그린)


class TradingApp:

    def __init__(self, root):
        self.root = root
        self.root.title("a-Mind Stock · AMS")
        self.root.geometry("1800x1000")
        self.root.minsize(1100, 700)
        self.root.configure(bg=BG)

        # 창 전체에 은은한 그라데이션을 깔아둡니다. (패널들 자체는 기존처럼 단색이라
        # 헤더 여백/좌우 여백 등 패널 밖 영역에서 그라데이션이 드러납니다)
        self.bg_canvas = tk.Canvas(root, highlightthickness=0, bd=0, bg=BG)
        self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.bg_canvas.bind("<Configure>", self._draw_gradient)

        # ====================================================
        # 기본 데이터
        # ====================================================

        self.previous_prices = {}
        self.price_history = defaultdict(lambda: deque(maxlen=60))
        self.selected_symbol = None
        self.news_data = []

        # 국가 컬럼의 국기 아이콘을 장 상태에 따라 바꾸기 위해 미리 초기화해둡니다.
        self.kr_open = False
        self.us_open = False

        self.access_token = get_access_token()
        self.data_manager = DataManager()

        # ====================================================
        # ttk 스타일
        # ====================================================

        self.setup_style()

        # ====================================================
        # 국기 아이콘 (실제 태극기/성조기를 픽셀로 직접 그려서 준비)
        # 이미지 참조를 인스턴스에 들고 있어야 GC로 사라지지 않습니다.
        # ====================================================

        self.flag_kr_open = self.make_kr_flag(dim=False)
        self.flag_kr_closed = self.make_kr_flag(dim=True)
        self.flag_us_open = self.make_us_flag(dim=False)
        self.flag_us_closed = self.make_us_flag(dim=True)

        # ====================================================
        # 상단 헤더
        # ====================================================

        header = tk.Frame(root, bg=BG)
        header.pack(fill="x", padx=22, pady=(18, 10))

        title_frame = tk.Frame(header, bg=BG)
        title_frame.pack(side="left")

        tk.Label(
            title_frame,
            text="a-Mind Stock · AMS",
            font=("Bahnschrift", 24, "bold"),
            fg=TEXT,
            bg=BG,
        ).pack(anchor="w")

        tk.Label(
            title_frame,
            text="AI-Powered Automated Trading System",
            font=("Bahnschrift", 9),
            fg=MUTED,
            bg=BG,
        ).pack(anchor="w", pady=(3, 0))

        # 상단 버튼
        button_frame = tk.Frame(header, bg=BG)
        button_frame.pack(side="right")

        self.refresh_button = tk.Button(
            button_frame,
            text="⟳  새로고침",
            command=self.manual_refresh,
            font=("Arial", 10, "bold"),
            fg=WHITE,
            bg=PANEL_2,
            activebackground=BORDER,
            activeforeground=WHITE,
            relief="flat",
            bd=0,
            padx=18,
            pady=9,
            cursor="hand2",
        )
        self.refresh_button.pack(side="left", padx=4)

        self.auto_button = tk.Button(
            button_frame,
            text="●  자동갱신 ON",
            command=self.toggle_auto_refresh,
            font=("Arial", 10, "bold"),
            fg=WHITE,
            bg="#166534",
            activebackground="#15803d",
            activeforeground=WHITE,
            relief="flat",
            bd=0,
            padx=18,
            pady=9,
            cursor="hand2",
        )
        self.auto_button.pack(side="left", padx=4)

        # ====================================================
        # 메인 영역
        # ====================================================

        main = tk.Frame(root, bg=BG)
        main.pack(fill="both", expand=True, padx=22, pady=8)

        # 왼쪽 68%, 오른쪽 32%
        left = tk.Frame(
            main,
            bg=PANEL,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        left.place(
            relx=0,
            rely=0,
            relwidth=0.495,
            relheight=1.0,
            x=0,
            y=0,
        )

        right = tk.Frame(
            main,
            bg=PANEL,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        right.place(
            relx=0.505,
            rely=0,
            relwidth=0.495,
            relheight=1.0,
            x=0,
            y=0,
        )

        # ====================================================
        # 왼쪽 - 주식 현황
        # ====================================================

        tk.Label(
            left,
            text="  주요 주식 현황",
            font=("Arial", 13, "bold"),
            fg=TEXT,
            bg=PANEL,
            anchor="w",
        ).pack(fill="x", padx=10, pady=(12, 7))

        # 미국 / 한국 시장 상태
        market_header = tk.Frame(left, bg=PANEL)
        market_header.pack(fill="x", padx=14, pady=(0, 6))

        self.us_status_label = tk.Label(
            market_header, text="🇺🇸 미국주식  •  확인 중",
            font=("Arial", 9, "bold"), fg=MUTED, bg=PANEL
        )
        self.us_status_label.pack(side="left")

        self.kr_status_label = tk.Label(
            market_header, text="🇰🇷 한국주식  •  확인 중",
            font=("Arial", 9, "bold"), fg=MUTED, bg=PANEL
        )
        self.kr_status_label.pack(side="right")

        table_frame = tk.Frame(left, bg=PANEL)
        table_frame.pack(fill="both", expand=True, padx=12)

        columns = ("symbol", "name", "price", "change", "change_rate")

        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="tree headings",  # "#0" 아이콘 컬럼에 실제 국기 이미지를 넣기 위해 tree 모드 사용
            height=13,
            style="Modern.Treeview",
            selectmode="browse",
        )

        self.tree.heading("#0", text="국가")
        self.tree.column("#0", width=42, minwidth=42, stretch=False, anchor="center")

        headers = {
            "symbol": "종목코드",
            "name": "종목명",
            "price": "현재가",
            "change": "변화",
            "change_rate": "변화율",
        }

        widths = {
            "symbol": 85,
            "name": 150,
            "price": 135,
            "change": 110,
            "change_rate": 95,
        }

        for col in columns:
            self.tree.heading(col, text=headers[col])
            self.tree.column(
                col, width=widths[col], anchor="center", stretch=True
            )

        self.tree.tag_configure("up", foreground=RED)
        self.tree.tag_configure("down", foreground=BLUE)
        self.tree.tag_configure("flat", foreground=BLACK)

        scrollbar = ttk.Scrollbar(
            table_frame, orient="vertical", command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.on_stock_selected)

        # ====================================================
        # 왼쪽 하단 - 선택 종목 그래프
        # ====================================================

        chart_header = tk.Frame(left, bg=PANEL)
        chart_header.pack(fill="x", padx=14, pady=(12, 3))

        self.chart_title = tk.Label(
            chart_header,
            text="📊 종목 차트  •  종목을 선택하세요",
            font=("Arial", 11, "bold"),
            fg=TEXT,
            bg=PANEL,
            anchor="w",
        )
        self.chart_title.pack(side="left")

        self.chart_info = tk.Label(
            chart_header,
            text="최근 60회 조회",
            font=("Arial", 9),
            fg=MUTED,
            bg=PANEL,
        )
        self.chart_info.pack(side="right")

        self.chart_canvas = tk.Canvas(
            left,
            height=210,
            bg=DEEP_BG,
            highlightthickness=0,
        )
        self.chart_canvas.pack(fill="x", padx=14, pady=(0, 12))
        self.chart_canvas.bind("<Configure>", lambda e: self.draw_chart())

        # ====================================================
        # 오른쪽 - 시장 지표
        # ====================================================

        tk.Label(
            right,
            text="  🌎 글로벌 시장 지표  •  GOLD: USD/oz",
            font=("Arial", 13, "bold"),
            fg=TEXT,
            bg=PANEL,
            anchor="w",
        ).pack(fill="x", padx=10, pady=(12, 7))

        market_frame = tk.Frame(right, bg=PANEL)
        market_frame.pack(fill="x", padx=14)
        self.market_labels = {}
        market_columns = [["WTI", "GOLD", "Brent", "USD/KRW"], ["SOX", "NASDAQ", "S&P500", "DXY"]]
        for col_index, names in enumerate(market_columns):
            col_frame = tk.Frame(market_frame, bg=PANEL)
            col_frame.pack(side="left", fill="both", expand=True, padx=(0, 4) if col_index == 0 else (4, 0))
            for name in names:
                row = tk.Frame(col_frame, bg=PANEL_2, highlightbackground=BORDER, highlightthickness=1)
                row.pack(fill="x", pady=2)
                name_label = tk.Label(row, text=name, font=("Arial", 9, "bold"), fg=TEXT, bg=PANEL_2, width=9, anchor="w")
                name_label.pack(side="left", padx=8, pady=5)
                value_label = tk.Label(row, text="데이터 확인 중...", font=("Consolas", 9), fg=MUTED, bg=PANEL_2, anchor="e")
                value_label.pack(side="right", padx=8, pady=5)
                self.market_labels[name] = value_label

        # ====================================================
        # 오른쪽 - 최신 뉴스
        # ====================================================

        tk.Label(right, text="  📰 최신 시장 뉴스", font=("Arial", 13, "bold"), fg=TEXT, bg=PANEL, anchor="w").pack(fill="x", padx=10, pady=(12, 6))

        news_frame = tk.Frame(right, bg=PANEL_2, highlightbackground=BORDER, highlightthickness=1)
        news_frame.pack(fill="x", padx=14, pady=(0, 10))

        news_columns = ("time", "source", "title", "symbols")
        self.news_tree = ttk.Treeview(news_frame, columns=news_columns, show="headings", height=7, style="Modern.Treeview")

        news_headers = {"time": "시간", "source": "출처", "title": "뉴스", "symbols": "관련종목"}
        news_widths = {"time": 65, "source": 90, "title": 500, "symbols": 105}

        for col in news_columns:
            self.news_tree.heading(col, text=news_headers[col])
            self.news_tree.column(col, width=news_widths[col], anchor="w", stretch=True)

        news_scrollbar = ttk.Scrollbar(news_frame, orient="vertical", command=self.news_tree.yview)
        self.news_tree.configure(yscrollcommand=news_scrollbar.set)
        self.news_tree.pack(side="left", fill="x", expand=True)
        news_scrollbar.pack(side="right", fill="y")

        self.news_tree.bind("<Double-1>", self.open_news_link)
        # ====================================================
        # 오른쪽 - 종합 판단 카드
        # ====================================================

        decision = tk.Frame(
            right,
            bg=DEEP_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        decision.pack(fill="x", padx=14, pady=14)

        self.total_score_label = tk.Label(
            decision,
            text="종합점수   0",
            font=("Arial", 14, "bold"),
            fg=TEXT,
            bg=DEEP_BG,
        )
        self.total_score_label.pack(pady=(13, 4))

        self.final_decision_label = tk.Label(
            decision,
            text="최종판단   대기",
            font=("Arial", 18, "bold"),
            fg=MUTED,
            bg=DEEP_BG,
        )
        self.final_decision_label.pack(pady=(2, 13))

        # ====================================================
        # 하단 상태바
        # ====================================================

        status_frame = tk.Frame(root, bg=STATUS_BAR_BG)
        status_frame.pack(fill="x", side="bottom")

        self.status_label = tk.Label(
            status_frame,
            text="시스템 준비 완료",
            font=("Arial", 9),
            fg=MUTED,
            bg=STATUS_BAR_BG,
            anchor="w",
        )
        self.status_label.pack(side="left", padx=22, pady=7)

        self.clock_label = tk.Label(
            status_frame,
            text="",
            font=("Consolas", 9),
            fg=MUTED,
            bg=STATUS_BAR_BG,
        )
        self.clock_label.pack(side="right", padx=22, pady=7)

        self.auto_refresh = True
        self.update_clock()
        self.update_loop()

        self.bg_canvas.tk.call("lower", self.bg_canvas._w)  # 그라데이션을 다른 모든 패널 뒤로 보냄

    # ========================================================
    # 배경 그라데이션
    # ========================================================

    def _draw_gradient(self, event=None):
        canvas = self.bg_canvas
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width <= 1 or height <= 1:
            return

        canvas.delete("gradient")

        r1, g1, b1 = (c >> 8 for c in self.root.winfo_rgb(GRADIENT_TOP))
        r2, g2, b2 = (c >> 8 for c in self.root.winfo_rgb(GRADIENT_BOTTOM))

        for i in range(height):
            t = i / height
            r = int(r1 + (r2 - r1) * t)
            g = int(g1 + (g2 - g1) * t)
            b = int(b1 + (b2 - b1) * t)
            canvas.create_line(0, i, width, i, fill=f"#{r:02x}{g:02x}{b:02x}", tags="gradient")

        canvas.tk.call("lower", canvas._w)

    # ========================================================
    # 스타일
    # ========================================================

    def setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "Modern.Treeview",
            background=STOCK_BG,
            fieldbackground=STOCK_BG,
            foreground=STOCK_TEXT,
            rowheight=24,
            borderwidth=0,
            font=("Arial", 9),
        )

        style.configure(
            "Modern.Treeview.Heading",
            background="#e2e8f0",
            foreground=STOCK_TEXT,
            font=("Arial", 9, "bold"),
            relief="flat",
            padding=7,
        )

        style.map(
            "Modern.Treeview",
            background=[("selected", "#cbd5e1")],
            foreground=[("selected", STOCK_TEXT)],
        )

        style.configure(
            "Vertical.TScrollbar",
            background=PANEL_2,
            troughcolor=PANEL,
            bordercolor=PANEL,
            arrowcolor=MUTED,
        )

    # ========================================================
    # 국기 아이콘 생성 (외부 이미지 파일 없이 tkinter.PhotoImage로 직접 그림)
    # ========================================================

    def make_kr_flag(self, width=26, height=18, dim=False):
        """태극기: 흰 바탕 + 태극 문양(빨강/파랑) + 네 모서리 괘(단순화)."""
        img = tk.PhotoImage(width=width, height=height)

        bg = "#d4d4d4" if dim else "#ffffff"
        red = "#9a9a9a" if dim else "#cd2e3a"
        blue = "#707070" if dim else "#0047a0"
        black = "#8a8a8a" if dim else "#111111"

        img.put(bg, to=(0, 0, width, height))

        cx, cy = width / 2, height / 2
        r = min(width, height) * 0.30

        for y in range(height):
            dy = y - cy
            for x in range(width):
                dx = x - cx
                dist = (dx * dx + dy * dy) ** 0.5
                if dist > r:
                    continue
                if dy <= 0:
                    color = red
                    if (dx * dx + (dy + r / 2) ** 2) ** 0.5 <= r / 2:
                        color = blue
                else:
                    color = blue
                    if (dx * dx + (dy - r / 2) ** 2) ** 0.5 <= r / 2:
                        color = red
                img.put(color, (x, y))

        # 네 모서리 괘(건/곤/감/리)를 짧은 막대로 단순화하여 표현
        # (아이콘이 워낙 작아서 정확한 효 배치보다는 "네 모서리에 무늬가 있다"는
        #  느낌을 살리는 수준의 단순화입니다)
        bar_w = max(4, width // 5)
        bar_h = 1
        gap = 1
        margin = 1
        block_h = bar_h * 3 + gap * 2

        def draw_trigram(x0, y0, broken_pattern):
            y = y0
            for broken in broken_pattern:
                if broken:
                    seg = max(1, (bar_w - 2) // 2)
                    img.put(black, to=(x0, y, x0 + seg, y + bar_h))
                    img.put(black, to=(x0 + bar_w - seg, y, x0 + bar_w, y + bar_h))
                else:
                    img.put(black, to=(x0, y, x0 + bar_w, y + bar_h))
                y += bar_h + gap

        draw_trigram(margin, margin, [False, False, False])  # 건(乾) - 좌상단
        draw_trigram(width - margin - bar_w, height - margin - block_h, [True, True, True])  # 곤(坤) - 우하단
        draw_trigram(width - margin - bar_w, margin, [False, True, False])  # 감(坎) - 우상단(근사)
        draw_trigram(margin, height - margin - block_h, [True, False, True])  # 리(離) - 좌하단(근사)

        return img

    def make_us_flag(self, width=26, height=18, dim=False):
        """성조기: 7줄 스트라이프 + 캔턴(별 영역) 단순화 버전."""
        img = tk.PhotoImage(width=width, height=height)

        red = "#8a8a8a" if dim else "#b22234"
        white = "#dedede" if dim else "#ffffff"
        blue = "#5e5e5e" if dim else "#3c3b6e"

        stripe_count = 7
        stripe_h = height / stripe_count
        for i in range(stripe_count):
            color = red if i % 2 == 0 else white
            y1 = round(i * stripe_h)
            y2 = height if i == stripe_count - 1 else round((i + 1) * stripe_h)
            img.put(color, to=(0, y1, width, y2))

        canton_w = round(width * 0.42)
        canton_h = round(stripe_h * 4)
        img.put(blue, to=(0, 0, canton_w, canton_h))

        for r in range(2):
            for c in range(3):
                x = round(canton_w * (c + 0.5) / 3)
                y = round(canton_h * (r + 0.5) / 2)
                img.put(white, (x, y))

        return img

    # ========================================================
    # 시계
    # ========================================================

    def update_clock(self):
        self.clock_label.config(text=time.strftime("%Y-%m-%d  %H:%M:%S"))
        if hasattr(self, "kr_status_label"):
            self.update_market_status_labels()
        self.root.after(1000, self.update_clock)

    # ========================================================
    # 자동 갱신 ON/OFF
    # ========================================================

    def toggle_auto_refresh(self):
        self.auto_refresh = not self.auto_refresh

        if self.auto_refresh:
            self.auto_button.config(
                text="●  자동갱신 ON",
                bg="#166534",
                activebackground="#15803d",
            )
            self.status_label.config(text="자동 갱신을 시작했습니다.")
        else:
            self.auto_button.config(
                text="○  자동갱신 OFF",
                bg="#475569",
                activebackground="#64748b",
            )
            self.status_label.config(text="자동 갱신이 일시정지되었습니다.")

    def manual_refresh(self):
        threading.Thread(target=self.fetch_stock_prices, daemon=True).start()
        threading.Thread(target=self.fetch_market_indicators, daemon=True).start()
        threading.Thread(target=self.fetch_news, daemon=True).start()
        self.status_label.config(text="수동 새로고침 요청")

    # ========================================================
    # 주기적인 업데이트
    # ========================================================

    def update_loop(self):
        if self.auto_refresh:
            if self.data_manager.should_update("stock_price"):
                threading.Thread(
                    target=self.fetch_stock_prices,
                    daemon=True,
                ).start()
                self.data_manager.mark_updated("stock_price")

            if self.data_manager.should_update("market_indicators"):
                threading.Thread(
                    target=self.fetch_market_indicators,
                    daemon=True,
                ).start()
                self.data_manager.mark_updated("market_indicators")
            if self.data_manager.should_update("news"):
                threading.Thread(target=self.fetch_news, daemon=True).start()
                self.data_manager.mark_updated("news")

        self.root.after(500, self.update_loop)

    # ========================================================
    # 주가 조회
    # ========================================================

    def fetch_stock_prices(self):
        if self.access_token is None:
            self.root.after(
                0,
                self.status_label.config,
                {"text": "❌ Access Token 발급 실패"},
            )
            return

        symbols = list(STOCKS.keys())
        stock_data = get_stock_prices(self.access_token, symbols)

        self.root.after(
            0,
            self.render_stock_prices,
            stock_data,
        )

    # ========================================================
    # 글로벌 시장 지표 조회
    # ========================================================

    def fetch_market_indicators(self):
        market_data = get_market_indicators()

        self.root.after(
            0,
            self.render_market_indicators,
            market_data,
        )
    # ========================================================
    # 뉴스 조회
    # ========================================================

    def fetch_news(self):
        try:
            import contextlib, io
            with contextlib.redirect_stdout(io.StringIO()):
                news_data = collect_news(limit_per_query=5)
            self.root.after(0, self.render_news, news_data)
        except Exception as e:
            print("❌ 뉴스 조회 실패:", e)
    # ========================================================
    # 주가 화면 출력
    # ========================================================

    def render_stock_prices(self, stock_data):
        if stock_data is None:
            self.status_label.config(text="❌ 주가 조회 실패")
            return

        stocks = parse_stock_data(stock_data)

        for row in self.tree.get_children():
            self.tree.delete(row)

        us_stocks = [stock for stock in stocks if stock.currency != "KRW"]
        kr_stocks = [stock for stock in stocks if stock.currency == "KRW"]

        self.update_market_status_labels()

        for stock in us_stocks:
            self.insert_stock_row(stock)

        for stock in kr_stocks:
            self.insert_stock_row(stock)

        self.status_label.config(
            text=f"주가 업데이트 완료  •  {time.strftime('%H:%M:%S')}"
        )

        self.draw_chart()

    def get_flag_image(self, currency):
        if currency == "KRW":
            return self.flag_kr_open if self.kr_open else self.flag_kr_closed
        return self.flag_us_open if self.us_open else self.flag_us_closed

    def insert_stock_row(self, stock):
        previous_price = self.previous_prices.get(stock.symbol)

        if previous_price is None:
            change = 0
            change_rate = 0
        else:
            change = stock.price - previous_price
            change_rate = (change / previous_price) * 100 if previous_price else 0

        self.price_history[stock.symbol].append(stock.price)

        if stock.currency == "KRW":
            price_text = f"₩ {stock.price:,.0f}"
            change_text = f"{change:+,.0f}"
        else:
            price_text = f"$ {stock.price:,.2f}"
            change_text = f"{change:+,.2f}"

        if change > 0:
            tag = "up"
        elif change < 0:
            tag = "down"
        else:
            tag = "flat"

        item = self.tree.insert(
            "", "end",
            image=self.get_flag_image(stock.currency),
            values=(stock.symbol, stock.name, price_text, change_text, f"{change_rate:+.2f}%"),
            tags=(tag,),
        )

        if stock.symbol == self.selected_symbol:
            self.tree.selection_set(item)
            self.tree.focus(item)

        self.previous_prices[stock.symbol] = stock.price

    def update_market_status_labels(self):
        now_kr = datetime.now(ZoneInfo("Asia/Seoul"))
        self.kr_open = now_kr.weekday() < 5 and dt_time(9, 0) <= now_kr.time() < dt_time(15, 30)

        now_us = datetime.now(ZoneInfo("America/New_York"))
        self.us_open = now_us.weekday() < 5 and dt_time(9, 30) <= now_us.time() < dt_time(16, 0)

        if self.kr_open:
            self.kr_status_label.config(text="🇰🇷 한국주식  •  Market Open", fg=RED)
        else:
            self.kr_status_label.config(text="🇰🇷 한국주식  •  Market Closed", fg=MUTED)

        if self.us_open:
            self.us_status_label.config(text="🇺🇸 미국주식  •  Market Open", fg=RED)
        else:
            self.us_status_label.config(text="🇺🇸 미국주식  •  Market Closed", fg=MUTED)

    # ========================================================
    # 종목 선택
    # ========================================================

    def on_stock_selected(self, event=None):
        selected = self.tree.selection()

        if not selected:
            return

        values = self.tree.item(selected[0], "values")

        if not values:
            return

        self.selected_symbol = values[0]

        name = values[1]
        self.chart_title.config(
            text=f"📊 {name} ({self.selected_symbol})"
        )

        self.draw_chart()

    # ========================================================
    # 종목 차트
    # ========================================================

    def draw_chart(self):
        canvas = self.chart_canvas
        canvas.delete("all")

        if not self.selected_symbol:
            self.draw_chart_message("종목을 선택하면 가격 추이가 표시됩니다.")
            return

        prices = list(self.price_history.get(self.selected_symbol, []))

        if len(prices) < 2:
            self.draw_chart_message("가격 데이터가 2개 이상 쌓이면 차트가 표시됩니다.")
            return

        width = max(canvas.winfo_width(), 500)
        height = max(canvas.winfo_height(), 210)

        left = 55
        right = 20
        top = 20
        bottom = 32

        min_price = min(prices)
        max_price = max(prices)

        if max_price == min_price:
            margin = max(abs(max_price) * 0.001, 1)
            min_price -= margin
            max_price += margin

        # 격자
        for i in range(5):
            y = top + (height - top - bottom) * i / 4
            canvas.create_line(
                left,
                y,
                width - right,
                y,
                fill="#1e293b",
            )

            value = max_price - (max_price - min_price) * i / 4
            canvas.create_text(
                left - 8,
                y,
                text=f"{value:,.2f}",
                fill=MUTED,
                anchor="e",
                font=("Consolas", 8),
            )

        # 선 색상: 마지막 변화 방향
        if prices[-1] > prices[-2]:
            line_color = RED
        elif prices[-1] < prices[-2]:
            line_color = BLUE
        else:
            line_color = "#64748b"

        points = []

        plot_width = width - left - right
        plot_height = height - top - bottom

        for i, price in enumerate(prices):
            x = left + plot_width * i / (len(prices) - 1)
            y = top + (max_price - price) / (max_price - min_price) * plot_height
            points.extend([x, y])

        canvas.create_line(
            *points,
            fill=line_color,
            width=2,
            smooth=True,
        )

        # 마지막 가격 표시
        last_x = points[-2]
        last_y = points[-1]

        canvas.create_oval(
            last_x - 4,
            last_y - 4,
            last_x + 4,
            last_y + 4,
            fill=line_color,
            outline="",
        )

        currency = ""
        if self.selected_symbol in STOCKS:
            # 현재 선택된 종목의 실제 통화는 테이블 데이터에서 표시되는 값으로 충분
            currency = ""

        self.chart_info.config(
            text=f"최근 {len(prices)}회 조회  •  현재 {prices[-1]:,.2f}{currency}"
        )

    def draw_chart_message(self, message):
        self.chart_canvas.create_text(
            self.chart_canvas.winfo_width() / 2,
            self.chart_canvas.winfo_height() / 2,
            text=message,
            fill=MUTED,
            font=("Arial", 10),
        )
        self.chart_info.config(text="최근 60회 조회")

    # ========================================================
    # 시장 지표 출력
    # ========================================================

    def render_market_indicators(self, market_data):
        if not market_data:
            return

        for name, data in market_data.items():
            change_rate = data["change_rate"]

            if change_rate > 0:
                arrow = "▲"
                text_color = RED
            elif change_rate < 0:
                arrow = "▼"
                text_color = BLUE
            else:
                arrow = "—"
                text_color = TEXT

            text = (
                f"{data['latest']:>12,.2f}  "
                f"{arrow} {change_rate:+.2f}%"
            )

            label = self.market_labels.get(name)

            if label:
                label.config(
                    text=text,
                    fg=text_color,
                )
    def render_news(self, news_data):
        if not news_data:
            return
        self.news_data = sorted(news_data, key=lambda x: x.get("published_at", ""), reverse=True)[:7]
        for row in self.news_tree.get_children():
            self.news_tree.delete(row)
        for i, article in enumerate(self.news_data):
            published_at = article.get("published_at", "")
            time_text = published_at[11:16] if len(published_at) >= 16 else published_at
            source = article.get("source", "") or "-"
            title = article.get("title", "") or "-"
            symbols = ", ".join(article.get("related_symbols", [])) or "-"
            self.news_tree.insert("", "end", iid=str(i), values=(time_text, source, title, symbols))
        self.status_label.config(text=f"뉴스 업데이트 완료  •  {time.strftime('%H:%M:%S')}")

    def open_news_link(self, event=None):
        import webbrowser

        selected = self.news_tree.selection()

        if not selected:
            return

        try:
            index = int(selected[0])
        except (TypeError, ValueError):
            return
        if 0 <= index < len(self.news_data):
            link = self.news_data[index].get("link")
            if link:
                webbrowser.open(link)

if __name__ == "__main__":
    root = tk.Tk()
    app = TradingApp(root)
    root.mainloop()
