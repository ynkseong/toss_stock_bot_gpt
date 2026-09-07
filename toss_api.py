import requests
from token_manager import get_access_token
from stock_data import StockData

BASE_URL = "https://openapi.tossinvest.com"

# ==========================================
# 관심 종목
# ==========================================

STOCKS = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "005380": "현대차",
    "035420": "NAVER",
    "035720": "카카오",
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
            price=int(stock["lastPrice"]),
            currency=stock["currency"],
            timestamp=stock["timestamp"]
        )

        stocks.append(standard_data)

    return stocks