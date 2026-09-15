"""
AlphaMindStock - 시가총액 Heatmap 데이터 모듈
무료 yfinance 기반. 미국 증시(NYSE/Nasdaq 등 미국 상장 종목) 중심으로 대표 대형주를 넓게 구성하고,
시장가치는 면적, 당일 등락률은 색상으로 표현한다.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import math
import time
import requests

# 카테고리별 미국 증시(미국 상장) 주요 종목. 한국(.KS) 및 해외 거래소(.L 등)는 제외.
# ticker: yfinance 심볼, label: 화면 표시명
HEATMAP_UNIVERSE = {
    "AI": [
        ("NVDA", "NVIDIA"), ("MSFT", "Microsoft"), ("GOOGL", "Alphabet"), ("META", "Meta"),
        ("AMZN", "Amazon"), ("AVGO", "Broadcom"), ("ORCL", "Oracle"), ("PLTR", "Palantir"),
        ("AMD", "AMD"), ("ARM", "Arm"), ("SMCI", "Super Micro"), ("TSM", "TSMC"),
        ("ASML", "ASML"), ("SNOW", "Snowflake"), ("AI", "C3.ai"),
    ],
    "반도체": [
        ("NVDA", "NVIDIA"), ("AVGO", "Broadcom"), ("TSM", "TSMC"), ("ASML", "ASML"),
        ("AMD", "AMD"), ("MU", "Micron"), ("INTC", "Intel"), ("QCOM", "Qualcomm"),
        ("TXN", "Texas Instruments"), ("AMAT", "Applied Materials"), ("LRCX", "Lam Research"),
        ("KLAC", "KLA"), ("MRVL", "Marvell"), ("ADI", "Analog Devices"), ("ON", "ON Semi"),
        ("NXPI", "NXP"),
    ],
    "소비재": [
        ("AMZN", "Amazon"), ("TSLA", "Tesla"), ("WMT", "Walmart"), ("COST", "Costco"),
        ("HD", "Home Depot"), ("MCD", "McDonald's"), ("NKE", "Nike"), ("SBUX", "Starbucks"),
        ("TGT", "Target"), ("LOW", "Lowe's"), ("TJX", "TJX"), ("KO", "Coca-Cola"),
        ("PEP", "PepsiCo"), ("PG", "P&G"), ("PM", "Philip Morris"), ("UL", "Unilever"),
    ],
    "통신": [
        ("T", "AT&T"), ("VZ", "Verizon"), ("TMUS", "T-Mobile"), ("CMCSA", "Comcast"),
        ("CHTR", "Charter"), ("SKM", "SK Telecom ADR"), ("KT", "KT"), ("DIS", "Disney"),
    ],
    "우주/방산": [
        ("LMT", "Lockheed Martin"), ("RTX", "RTX"), ("NOC", "Northrop Grumman"), ("GD", "General Dynamics"),
        ("BA", "Boeing"), ("HII", "Huntington Ingalls"), ("LHX", "L3Harris"), ("TDG", "TransDigm"),
        ("HEI", "HEICO"), ("RKLB", "Rocket Lab"), ("ASTS", "AST SpaceMobile"), ("PL", "Planet Labs"),
        ("KTOS", "Kratos"), ("AVAV", "AeroVironment"), ("LDOS", "Leidos"), ("TXT", "Textron"),
    ],
    "헬스": [
        ("UNH", "UnitedHealth"), ("LLY", "Eli Lilly"), ("JNJ", "Johnson & Johnson"), ("ABBV", "AbbVie"),
        ("MRK", "Merck"), ("PFE", "Pfizer"), ("BMY", "Bristol Myers"), ("AMGN", "Amgen"),
        ("GILD", "Gilead"), ("MDT", "Medtronic"), ("ABT", "Abbott"), ("TMO", "Thermo Fisher"),
        ("DHR", "Danaher"), ("ISRG", "Intuitive Surgical"), ("SYK", "Stryker"), ("CVS", "CVS Health"),
    ],
    "바이오/건강": [
        ("NVO", "Novo Nordisk"), ("VRTX", "Vertex"), ("REGN", "Regeneron"), ("GSK", "GSK"),
        ("AZN", "AstraZeneca"), ("BIIB", "Biogen"), ("MRNA", "Moderna"), ("BNTX", "BioNTech"),
        ("ILMN", "Illumina"), ("ALNY", "Alnylam"), ("CRSP", "CRISPR"), ("INCY", "Incyte"),
        ("RPRX", "Royalty Pharma"), ("HIMS", "Hims & Hers"), ("DXCM", "Dexcom"), ("VEEV", "Veeva"),
    ],
    "금융": [
        ("JPM", "JPMorgan"), ("BAC", "Bank of America"), ("WFC", "Wells Fargo"), ("C", "Citigroup"),
        ("GS", "Goldman Sachs"), ("MS", "Morgan Stanley"), ("BLK", "BlackRock"), ("SCHW", "Charles Schwab"),
        ("AXP", "American Express"), ("V", "Visa"), ("MA", "Mastercard"), ("PYPL", "PayPal"),
        ("COF", "Capital One"), ("SPGI", "S&P Global"), ("CME", "CME Group"), ("ICE", "ICE"),
    ],
}

_cache = {"data": None, "timestamp": 0.0}
CACHE_SECONDS = 10  # 실제 Yahoo Finance 데이터 조회 간격 (화면도 10초마다 갱신)


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


# 시가총액은 Yahoo Chart API에서 제공되지 않으므로 화면 면적 계산용 기준값을 둡니다.
# 실제 가격은 매 조회 시 Chart API에서 가져오고, 면적은 대형주 상대규모가 유지되도록 사용합니다.
MARKET_CAP_BASE_B = {
    "NVDA": 4600, "MSFT": 3800, "GOOGL": 3000, "META": 1800, "AMZN": 2700,
    "AVGO": 1900, "ORCL": 1000, "PLTR": 420, "AMD": 330, "ARM": 280, "SMCI": 35,
    "TSM": 1500, "ASML": 430, "SNOW": 65, "AI": 5,
    "MU": 210, "INTC": 110, "QCOM": 210, "TXN": 190, "AMAT": 250, "LRCX": 150,
    "KLAC": 180, "MRVL": 80, "ADI": 100, "ON": 35, "NXPI": 30,
    "TSLA": 1200, "WMT": 1100, "COST": 450, "HD": 390, "MCD": 230, "NKE": 100,
    "SBUX": 100, "TGT": 20, "LOW": 140, "TJX": 180, "KO": 330, "PEP": 220,
    "PG": 360, "PM": 260, "UL": 150,
    "T": 170, "VZ": 190, "TMUS": 300, "CMCSA": 100, "CHTR": 25, "SKM": 8,
    "KT": 7, "DIS": 190,
    "LMT": 120, "RTX": 230, "NOC": 75, "GD": 90, "BA": 160, "HII": 12,
    "LHX": 25, "TDG": 75, "HEI": 35, "RKLB": 20, "ASTS": 15, "PL": 1.5,
    "KTOS": 8, "AVAV": 15, "LDOS": 20, "TXT": 20,
    "UNH": 300, "LLY": 900, "JNJ": 380, "ABBV": 350, "MRK": 230, "PFE": 150,
    "BMY": 100, "AMGN": 85, "GILD": 160, "MDT": 110, "ABT": 220, "TMO": 220,
    "DHR": 180, "ISRG": 220, "SYK": 170, "CVS": 90,
    "NVO": 300, "VRTX": 100, "REGN": 75, "GSK": 100, "AZN": 250, "BIIB": 20,
    "MRNA": 25, "BNTX": 30, "ILMN": 20, "ALNY": 40, "CRSP": 8, "INCY": 15,
    "RPRX": 15, "HIMS": 15, "DXCM": 20, "VEEV": 30,
    "JPM": 900, "BAC": 350, "WFC": 300, "C": 180, "GS": 250, "MS": 220,
    "BLK": 170, "SCHW": 150, "AXP": 220, "V": 750, "MA": 600, "PYPL": 70,
    "COF": 120, "SPGI": 180, "CME": 100, "ICE": 100,
}

_CHART_URLS = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=2d&interval=1d&events=history",
    "https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?range=2d&interval=1d&events=history",
)
_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/153 Safari/537.36"})


def _fetch_one(item):
    """Yahoo Finance의 Chart API를 직접 사용해 crumb 인증 문제를 피합니다."""
    ticker, label = item
    if "." in ticker:
        return None

    payload = None
    for url in _CHART_URLS:
        try:
            r = _SESSION.get(url.format(ticker=ticker), timeout=8)
            if r.status_code == 200:
                payload = r.json()
                break
        except Exception:
            continue

    try:
        result = payload["chart"]["result"][0]
        meta = result.get("meta", {})
        closes = (result.get("indicators", {}).get("quote", [{}])[0].get("close", []) or [])
        closes = [float(x) for x in closes if x is not None]

        price = float(meta.get("regularMarketPrice") or (closes[-1] if closes else 0))
        prev = float(meta.get("chartPreviousClose") or (closes[-2] if len(closes) >= 2 else 0))
        if price <= 0 or prev <= 0:
            return None

        market_cap = MARKET_CAP_BASE_B.get(ticker, 1.0) * 1e9
        change_rate = (price - prev) / prev * 100
        return {
            "ticker": ticker,
            "label": label,
            "market_cap": market_cap,
            "price": price,
            "change_rate": change_rate,
        }
    except Exception:
        return None

def get_heatmap_data(force=False):
    """화면과 외부 데이터 조회를 모두 10초 간격으로 동작."""
    now = time.time()
    if _cache["data"] is not None and now - _cache["timestamp"] < CACHE_SECONDS:
        return _cache["data"]

    previous = _cache["data"] or {}
    result = {}
    jobs = [(category, item) for category, items in HEATMAP_UNIVERSE.items() for item in items]

    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = {pool.submit(_fetch_one, item): category for category, item in jobs}
        for future in as_completed(futures):
            category = futures[future]
            try:
                data = future.result()
            except Exception:
                data = None
            if data:
                result.setdefault(category, []).append(data)

    # 일시적으로 빠진 종목은 직전 정상 데이터를 유지합니다.
    for category, old_items in previous.items():
        current_tickers = {x["ticker"] for x in result.get(category, [])}
        for old in old_items:
            if old["ticker"] not in current_tickers:
                result.setdefault(category, []).append(old)

    for category in result:
        result[category].sort(key=lambda x: x["market_cap"], reverse=True)

    # 전체 조회 실패 시 빈 Heatmap으로 덮어쓰지 않습니다.
    if result:
        _cache["data"] = result
        _cache["timestamp"] = now
        return result
    return previous


if __name__ == "__main__":
    data = get_heatmap_data(force=True)
    for category, items in data.items():
        print(f"\n[{category}] {len(items)}종목")
        for x in items[:10]:
            print(f"{x['label']:20} {x['market_cap']/1e9:10.1f}B {x['change_rate']:+.2f}%")
