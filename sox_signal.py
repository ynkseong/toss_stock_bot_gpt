import yfinance as yf


def get_sox_condition():
    """
    필라델피아 반도체지수(SOX) 최근 종가 2개를 비교해
    1일봉 기준 상승 여부를 반환한다.

    반환값 예시:
    {
        "latest_close": 5123.45,
        "previous_close": 5050.10,
        "change": 73.35,
        "change_rate": 1.45,
        "is_up": True,
    }
    """
    try:
        sox = yf.Ticker("^SOX")
        history = sox.history(period="5d")

        if len(history) < 2:
            print("❌ SOX 데이터가 충분하지 않습니다.")
            return None

        latest_close = float(history["Close"].iloc[-1])
        previous_close = float(history["Close"].iloc[-2])

        change = latest_close - previous_close
        change_rate = (change / previous_close) * 100
        is_up = latest_close > previous_close

        return {
            "latest_close": latest_close,
            "previous_close": previous_close,
            "change": change,
            "change_rate": change_rate,
            "is_up": is_up,
        }

    except Exception as e:
        print("❌ SOX 지수 조회 실패:", e)
        return None


if __name__ == "__main__":
    result = get_sox_condition()
    print(result)