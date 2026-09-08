import tkinter as tk
from tkinter import ttk
import threading
import time

from token_manager import get_access_token
from toss_api import (
    get_stock_prices,
    parse_stock_data,
    get_investor_trading,
    parse_investor_trading,
    STOCKS,
)
from sox_signal import get_sox_condition
from decision_engine import evaluate_symbol


class TradingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("주식매매프로그램")
        self.root.geometry("950x520")

        self.previous_prices = {}
        self.access_token = get_access_token()

        # SOX 조건 표시 영역
        self.sox_label = tk.Label(root, text="SOX 지수 확인 중...", font=("Arial", 12, "bold"))
        self.sox_label.pack(pady=10)

        # 종목 테이블
        columns = ("symbol", "name", "price", "change", "change_rate", "investor", "signal")
        self.tree = ttk.Treeview(root, columns=columns, show="headings", height=15)

        headers = {
            "symbol": "종목코드",
            "name": "종목명",
            "price": "현재가",
            "change": "변화",
            "change_rate": "변화율",
            "investor": "투자자 동향",
            "signal": "시그널",
        }
        widths = {
            "symbol": 90, "name": 130, "price": 110, "change": 90,
            "change_rate": 80, "investor": 260, "signal": 80,
        }
        for col in columns:
            self.tree.heading(col, text=headers[col])
            self.tree.column(col, width=widths[col], anchor="center")

        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        # BUY 시그널 강조를 위한 태그
        self.tree.tag_configure("buy", background="#d9f2d9")

        self.status_label = tk.Label(root, text="", font=("Arial", 9), fg="gray")
        self.status_label.pack(pady=5)

        self.update_loop()

    def update_loop(self):
        threading.Thread(target=self.fetch_and_update, daemon=True).start()
        self.root.after(5000, self.update_loop)

    def fetch_and_update(self):
        if self.access_token is None:
            self.root.after(0, self.status_label.config, {"text": "❌ Access Token 발급 실패"})
            return

        symbols = list(STOCKS.keys())
        stock_data = get_stock_prices(self.access_token, symbols)

        investor_data = {}
        for symbol in ["005930", "000660", "005380", "035420", "035720"]:
            raw_data = get_investor_trading(self.access_token, symbol)
            if raw_data is not None:
                parsed = parse_investor_trading(raw_data)
                if parsed is not None:
                    investor_data[symbol] = parsed

        sox_condition = get_sox_condition()

        self.root.after(0, self.render, stock_data, investor_data, sox_condition)

    def render(self, stock_data, investor_data, sox_condition):
        # SOX 지수 표시
        if sox_condition:
            arrow = "🔺" if sox_condition["is_up"] else "🔻"
            self.sox_label.config(
                text=(
                    f"SOX 지수 {arrow} {sox_condition['latest_close']:.2f} "
                    f"({sox_condition['change_rate']:+.2f}%) "
                    f"— {'상승' if sox_condition['is_up'] else '하락/보합'}"
                )
            )
        else:
            self.sox_label.config(text="SOX 지수 데이터를 불러올 수 없습니다.")

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
                change_rate = (change / previous_price) * 100 if previous_price else 0

            if stock.currency == "KRW":
                price_text = f"{stock.price:,.0f} 원"
                change_text = f"{change:,.0f}"
            else:
                price_text = f"${stock.price:,.2f}"
                change_text = f"{change:,.2f}"

            investor = investor_data.get(stock.symbol)
            if investor:
                investor_text = (
                    f"개인 {investor['individual']:+,} / "
                    f"외국인 {investor['foreigner']:+,} / "
                    f"기관 {investor['institution']:+,}"
                )
            else:
                investor_text = "-"

            signal = evaluate_symbol(stock.symbol, sox_condition)
            tags = ("buy",) if signal == "BUY" else ()

            self.tree.insert(
                "", "end",
                values=(
                    stock.symbol, stock.name, price_text, change_text,
                    f"{change_rate:+.2f}%", investor_text, signal,
                ),
                tags=tags,
            )

            self.previous_prices[stock.symbol] = stock.price

        self.status_label.config(text=f"마지막 업데이트: {time.strftime('%H:%M:%S')}")


if __name__ == "__main__":
    root = tk.Tk()
    app = TradingApp(root)
    root.mainloop()