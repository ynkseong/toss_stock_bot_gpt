import yfinance as yf


# ==========================================
# 글로벌 시장 지표
# ==========================================

MARKET_INDICATORS = {
    "SOX": "^SOX",
    "NASDAQ": "^IXIC",
    "S&P500": "^GSPC",

    # TradingView 기준: TVC:DXY
    "DXY": "DX-Y.NYB",

    "WTI": "CL=F",
    "Brent": "BZ=F",
    "USD/KRW": "USDKRW=X",
}


# ==========================================
# 지표 하나 조회
# ==========================================

def get_market_indicator(name, ticker):

    try:

        data = yf.Ticker(ticker).history(
            period="5d",
            interval="1d"
        )

        if len(data) < 2:
            print(f"❌ {name} 데이터가 충분하지 않습니다.")
            return None

        latest = float(data["Close"].iloc[-1])
        previous = float(data["Close"].iloc[-2])

        change = latest - previous

        change_rate = (
            change / previous
        ) * 100 if previous else 0

        return {
            "name": name,
            "ticker": ticker,
            "latest": latest,
            "previous": previous,
            "change": change,
            "change_rate": change_rate,
            "is_up": latest > previous,
        }

    except Exception as e:

        print(
            f"❌ {name} 조회 실패:",
            e
        )

        return None


# ==========================================
# 전체 시장 지표 조회
# ==========================================

def get_market_indicators():

    results = {}

    for name, ticker in MARKET_INDICATORS.items():

        result = get_market_indicator(
            name,
            ticker
        )

        if result is not None:
            results[name] = result

    return results


# ==========================================
# 테스트
# ==========================================

if __name__ == "__main__":

    print("🌎 글로벌 시장 지표 조회")
    print()

    indicators = get_market_indicators()

    for name, data in indicators.items():

        arrow = (
            "🔺"
            if data["is_up"]
            else "🔻"
        )

        print(
            f"{name:<10} "
            f"{data['latest']:>12.2f} "
            f"{arrow} "
            f"{data['change_rate']:+.2f}%"
        )