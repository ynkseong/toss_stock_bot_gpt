import tkinter as tk
from tkinter import ttk
import threading
import time

from token_manager import get_access_token
from toss_api import get_stock_prices, parse_stock_data, STOCKS
from market_indicators import get_market_indicators
from data_manager import DataManager


class TradingApp:

    def __init__(self, root):
        self.root = root
        self.root.title("주식매매프로그램")
        self.root.geometry("1200x650")

        # ==========================================
        # 기본 데이터
        # ==========================================

        self.previous_prices = {}
        self.access_token = get_access_token()
        self.data_manager = DataManager()

        # ==========================================
        # 제목
        # ==========================================

        title_label = tk.Label(
            root, text="📈 주식매매프로그램", font=("Arial", 18, "bold")
        )
        title_label.pack(pady=10)

        # ==========================================
        # 메인 화면
        # 왼쪽 / 오른쪽 분할
        # ==========================================

        main_frame = ttk.Frame(root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # 왼쪽 영역
        left_frame = ttk.LabelFrame(main_frame, text="📊 주요 주식 현황")
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        # 오른쪽 영역
        right_frame = ttk.LabelFrame(main_frame, text="🧠 조건 판단 현황")
        right_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))

        # ==========================================
        # 왼쪽 - 주식 테이블
        # ==========================================

        columns = ("symbol", "name", "price", "change", "change_rate")

        self.tree = ttk.Treeview(
            left_frame, columns=columns, show="headings", height=20
        )

        headers = {
            "symbol": "종목코드",
            "name": "종목명",
            "price": "현재가",
            "change": "변화",
            "change_rate": "변화율",
        }

        widths = {
            "symbol": 80,
            "name": 120,
            "price": 110,
            "change": 100,
            "change_rate": 80,
        }

        for col in columns:
            self.tree.heading(col, text=headers[col])
            self.tree.column(col, width=widths[col], anchor="center")

        self.tree.pack(fill="both", expand=True, padx=5, pady=5)

        # ==========================================
        # 왼쪽 - 시장 지표
        # ==========================================

        market_frame = ttk.LabelFrame(left_frame, text="🌎 시장 지표")
        market_frame.pack(fill="x", padx=5, pady=5)

        self.market_labels = {}

        market_names = [
            "SOX",
            "NASDAQ",
            "S&P500",
            "DXY",
            "WTI",
            "Brent",
            "USD/KRW",
        ]

        for name in market_names:
            label = tk.Label(
                market_frame,
                text=f"{name:<10} 데이터 확인 중...",
                font=("Consolas", 10),
                anchor="w",
            )
            label.pack(fill="x", padx=10, pady=2)
            self.market_labels[name] = label

        # ==========================================
        # 오른쪽 - 조건 테이블
        # ==========================================

        condition_columns = ("condition", "value", "status", "score")

        self.condition_tree = ttk.Treeview(
            right_frame,
            columns=condition_columns,
            show="headings",
            height=12,
        )

        condition_headers = {
            "condition": "조건",
            "value": "현재값",
            "status": "판단",
            "score": "점수",
        }

        condition_widths = {
            "condition": 120,
            "value": 120,
            "status": 90,
            "score": 70,
        }

        for col in condition_columns:
            self.condition_tree.heading(col, text=condition_headers[col])
            self.condition_tree.column(
                col,
                width=condition_widths[col],
                anchor="center",
            )

        self.condition_tree.pack(fill="both", expand=True, padx=5, pady=5)

        # ==========================================
        # 오른쪽 - 종합 판단
        # ==========================================

        decision_frame = ttk.LabelFrame(right_frame, text="🎯 종합 판단")
        decision_frame.pack(fill="x", padx=5, pady=5)

        self.total_score_label = tk.Label(
            decision_frame,
            text="종합점수: 0",
            font=("Arial", 14, "bold"),
        )
        self.total_score_label.pack(pady=5)

        self.final_decision_label = tk.Label(
            decision_frame,
            text="최종판단: 대기",
            font=("Arial", 16, "bold"),
        )
        self.final_decision_label.pack(pady=5)

        # ==========================================
        # 상태
        # ==========================================

        self.status_label = tk.Label(
            root,
            text="",
            font=("Arial", 9),
            fg="gray",
        )
        self.status_label.pack(pady=5)

        # ==========================================
        # 업데이트 시작
        # ==========================================

        self.update_loop()

    # ==========================================
    # 주기적인 업데이트 관리
    # ==========================================

    def update_loop(self):
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

        self.root.after(500, self.update_loop)

    # ==========================================
    # 주가 조회
    # ==========================================

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

    # ==========================================
    # 글로벌 시장 지표 조회
    # ==========================================

    def fetch_market_indicators(self):
        market_data = get_market_indicators()

        self.root.after(
            0,
            self.render_market_indicators,
            market_data,
        )

    # ==========================================
    # 주가 화면 출력
    # ==========================================

    def render_stock_prices(self, stock_data):
        if stock_data is None:
            self.status_label.config(text="❌ 주가 조회 실패")
            return

        stocks = parse_stock_data(stock_data)

        for row in self.tree.get_children():
            self.tree.delete(row)

        for stock in stocks:
            previous_price = self.previous_prices.get(stock.symbol)

            if previous_price is None:
                change = 0
                change_rate = 0
            else:
                change = stock.price - previous_price
                change_rate = (
                    (change / previous_price) * 100
                    if previous_price
                    else 0
                )

            if stock.currency == "KRW":
                price_text = f"KRW {stock.price:,.0f}"
                change_text = f"{change:+,.0f}"
            else:
                price_text = f"USD {stock.price:,.2f}"
                change_text = f"{change:+,.2f}"

            self.tree.insert(
                "",
                "end",
                values=(
                    stock.symbol,
                    stock.name,
                    price_text,
                    change_text,
                    f"{change_rate:+.2f}%",
                ),
            )

            self.previous_prices[stock.symbol] = stock.price

        self.status_label.config(
            text=f"주가 업데이트: {time.strftime('%H:%M:%S')}"
        )

    # ==========================================
    # 시장 지표 화면 출력
    # ==========================================

    def render_market_indicators(self, market_data):
        if not market_data:
            return

        for name, data in market_data.items():
            arrow = "🔺" if data["is_up"] else "🔻"

            text = (
                f"{name:<10}"
                f"{data['latest']:>12,.2f}  "
                f"{arrow} "
                f"{data['change_rate']:+.2f}%"
            )

            label = self.market_labels.get(name)

            if label:
                label.config(text=text)


if __name__ == "__main__":
    root = tk.Tk()
    app = TradingApp(root)
    root.mainloop()