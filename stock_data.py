from dataclasses import dataclass

@dataclass
class StockData:

    symbol: str
    name: str
    price: int
    currency: str
    timestamp: str