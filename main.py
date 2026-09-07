import time
from token_manager import get_access_token
from toss_api import get_stock_prices, parse_stock_data, STOCKS


def display_stocks(stocks, previous_prices):
    print("\033[2J\033[H", end="")

    print("╔══════════════════════════════════════════════════╗")
    print("║             📊 TOSS STOCK MONITOR              ║")
    print("╠══════════════════════════════════════════════════╣")
    print("║ 종목          현재가          변화        변화율 ║")
    print("╠══════════════════════════════════════════════════╣")

    for stock in stocks:
        current_price = stock.price
        previous_price = previous_prices.get(stock.symbol)

        if previous_price is None:
            change = 0
            change_rate = 0
        else:
            change = current_price - previous_price
            change_rate = (change / previous_price) * 100

        print(
            f"║ {stock.name:<10}"
            f"{current_price:>12,}원"
            f"{change:>12,}원"
            f"{change_rate:>8.2f}% ║"
        )

    print("╚══════════════════════════════════════════════════╝")
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

            if stock_data is not None:

                # StockData로 변환
                stocks = parse_stock_data(stock_data)

                # 화면 출력
                display_stocks(stocks, previous_prices)

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