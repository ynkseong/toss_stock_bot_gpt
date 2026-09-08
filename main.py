from token_manager import get_access_token
import time
from toss_api import (
    get_stock_prices,
    parse_stock_data,
    get_investor_trading,
    parse_investor_trading,
    STOCKS,
)

def display_stocks(stocks, previous_prices, investor_data):

    print("\033[2J\033[H", end="")
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║ 종목코드        현재가          변화        변화율        종목명     ║")
    print("╠═══════════════════════════════════════════════════════════════════════")

    for stock in stocks:
        current_price = stock.price
        previous_price = previous_prices.get(stock.symbol)

        if previous_price is None:
            change = 0
            change_rate = 0
        else:
            change = current_price - previous_price
            change_rate = (change / previous_price) * 100

        # 통화 표시
        if stock.currency == "KRW":
            price_text = f"KRW {current_price:,.0f}"
            change_text = f"KRW {change:,.0f}"
        else:
            price_text = f"USD {current_price:,.2f}"
            change_text = f"USD {change:,.2f}"

        investor = investor_data.get(stock.symbol)

        if investor:
            individual = investor["individual"]
            foreigner = investor["foreigner"]
            institution = investor["institution"]

            print(
                f"║ {'':10}"
                f"개인 {individual:+,}"
                f"  외국인 {foreigner:+,}"
                f"  기관 {institution:+,}"
                f"{'':>20}"
            )

        print(
            f"║ {stock.symbol:<10}"
            f"{price_text:>16}"
            f"{change_text:>16}"
            f"{change_rate:>10.2f}%"
            f"    {stock.name:<20}"
        )

    print("╚══════════════════════════════════════════════════════════════════════")
    print()
    print("🔄 5초마다 자동 갱신됩니다.")
    print("🛑 종료하려면 Ctrl + C")

def main():
    print("🚀 주식매매프로그램 시작")

    access_token = get_access_token()

    if access_token is None:
        print("❌ Access Token 발급 실패")
        return

    symbols = list(STOCKS.keys())

    # 직전 가격 저장
    previous_prices = {}

    try:
        while True:

            # 주가 조회
            stock_data = get_stock_prices(access_token, symbols)

            investor_data = {}

            for symbol in ["005930", "000660", "005380", "035420", "035720"]:
                raw_data = get_investor_trading(access_token, symbol)

                if raw_data is not None:
                    parsed_data = parse_investor_trading(raw_data)

                    if parsed_data is not None:
                        investor_data[symbol] = parsed_data

            if stock_data is not None:

                # StockData로 변환
                stocks = parse_stock_data(stock_data)

                # 화면 출력
                display_stocks(stocks, previous_prices, investor_data)

                # 현재 가격을 다음 비교를 위해 저장
                for stock in stocks:
                    previous_prices[stock.symbol] = stock.price

            else:
                print("❌ 주가 조회 실패")

            time.sleep(5)

    except KeyboardInterrupt:
        print()
        print("🛑 프로그램을 종료합니다.")


if __name__ == "__main__":
    main()