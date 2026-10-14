import requests
from token_manager import get_access_token
from stock_data import StockData

BASE_URL = "https://openapi.tossinvest.com"

# ==========================================
# 관심 종목
# ==========================================

STOCKS = {
    "005930": "Samsung Electronics",
    "000660": "SK Hynix",
    "005380": "Hyundai Motor",
    "035420": "NAVER",
    "035720": "Kakao",
    "042700": "Hanmi Semiconductor",
    "009150": "Samsung Electro-Mechanics",
    "064400": "LG CNS",
    "010120": "LS ELECTRIC",
    "NVDA": "NVIDIA",
    "INTC": "Intel",
    "SNDK": "SanDisk",
    "MU": "Micron Tech.",
    "AMD": "AMD",
    "META": "Meta Platforms",
    "AMZN": "Amazon",
    "QCOM": "Qualcomm",
    "DELL": "Dell Technologies",
    "GOOGL": "Alphabet",
    "MSFT": "Microsoft",
    "PLTR": "Palantir Technologies",
    "MRVL": "Marvell Technology",
    "AAPL": "Apple",
    "AMAT": "Applied Materials",
    "TSLA": "Tesla",
    "AVGO": "Broadcom",
    "SOXL": "Directional Daily Semiconductor Bull 3X",
    "SOXS": "Directional Daily Semiconductor Bear 3X"
    }

# ==========================================
# 여러 종목 현재가 조회
# ==========================================

def get_stock_prices(access_token, symbols):

    symbol_list = ",".join(symbols)

    url = f"{BASE_URL}/api/v1/prices?symbols={symbol_list}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print("❌ 주가 조회 실패")
        print("상태 코드:", response.status_code)
        print(response.text)
        return None

    return response.json()

def get_investor_trading(access_token, symbol):
    url = f"{BASE_URL}/api/v1/stocks/{symbol}/investor-trading"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"❌ {symbol} 투자자별 매매동향 조회 실패")
        print("상태 코드:", response.status_code)
        print(response.text)
        return None

    return response.json()

def parse_investor_trading(investor_data):
    if not investor_data:
        return None

    records = investor_data.get("result", {}).get("records", [])

    if not records:
        return None

    latest = records[0]

    return {
        "date": latest["date"],
        "individual": int(latest["individual"]["netBuyVolume"]),
        "foreigner": int(latest["foreigner"]["netBuyVolume"]),
        "institution": int(latest["institution"]["netBuyVolume"]),
    }

# ==========================================
# API 데이터를 표준 데이터 구조로 변환
# ==========================================

def parse_stock_data(stock_data):

    stocks = []

    for stock in stock_data["result"]:

        symbol = stock["symbol"]

        standard_data = StockData(
            symbol=symbol,
            name=STOCKS.get(symbol, symbol),
            price=float(stock["lastPrice"]),
            currency=stock["currency"],
            timestamp=stock["timestamp"]
        )

        stocks.append(standard_data)

    return stocks