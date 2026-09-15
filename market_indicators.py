import time
import requests

# ==========================================
# 글로벌 시장 지표
# Yahoo Finance chart API를 직접 사용합니다.
# yfinance를 사용하지 않아 Crumb 401/429 문제를 피합니다.
# ==========================================
MARKET_INDICATORS = {
    "SOX": "^SOX",
    "NASDAQ": "^IXIC",
    "S&P500": "^GSPC",
    "DXY": "DX-Y.NYB",
    "WTI": "CL=F",
    "Brent": "BZ=F",
    "GOLD": "GC=F",
    "USD/KRW": "KRW=X",
}

CACHE_SECONDS = 30
_cache = {}
_session = requests.Session()
_session.headers.update({"User-Agent": "Mozilla/5.0"})


def _fetch_chart(ticker):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"range": "5d", "interval": "1d", "events": "history"}
    response = _session.get(url, params=params, timeout=10)
    response.raise_for_status()
    payload = response.json()
    result = payload.get("chart", {}).get("result")
    if not result:
        return None
    closes = result[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
    closes = [float(x) for x in closes if x is not None]
    if len(closes) < 2:
        return None
    return closes[-1], closes[-2]


def get_market_indicator(name, ticker):
    now = time.time()
    cached = _cache.get(name)
    if cached and now - cached["time"] < CACHE_SECONDS:
        return cached["data"]

    try:
        values = _fetch_chart(ticker)
        if values is None:
            raise ValueError("데이터가 충분하지 않습니다.")

        latest, previous = values
        change = latest - previous
        change_rate = (change / previous) * 100 if previous else 0
        data = {
            "name": name,
            "ticker": ticker,
            "latest": latest,
            "previous": previous,
            "change": change,
            "change_rate": change_rate,
            "is_up": latest > previous,
        }
        _cache[name] = {"time": now, "data": data}
        return data
    except Exception as e:
        # 일시적인 Yahoo 제한이 있어도 마지막 정상값 유지
        if cached:
            print(f"⚠️ {name} 조회 실패: {e} • 마지막 정상 데이터 유지")
            return cached["data"]
        print(f"❌ {name} 조회 실패: {e}")
        return None


def get_market_indicators():
    results = {}
    for name, ticker in MARKET_INDICATORS.items():
        result = get_market_indicator(name, ticker)
        if result is not None:
            results[name] = result
    return results


if __name__ == "__main__":
    print("🌎 글로벌 시장 지표 조회")
    print()
    indicators = get_market_indicators()
    for name, data in indicators.items():
        arrow = "🔺" if data["is_up"] else "🔻"
        print(f"{name:<10} {data["latest"]:>12.2f} {arrow} {data["change_rate"]:+.2f}%")
