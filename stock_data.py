from dataclasses import dataclass

@dataclass
class StockData:

    symbol: str
    name: str
    price: float
    currency: str
    timestamp: str