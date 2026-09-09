import time

class DataManager:

    def __init__(self):
        # 데이터별 마지막 갱신 시간
        self.last_update = {}

        # 데이터별 갱신 주기(초)
        self.intervals = {
            "stock_price": 3,
            "investor": 180,
            "sox": 180,
            "exchange_rate": 180,
            "market_indicators": 180,
            "news": 300,
            "interest_rate": 86400,
        }

    def should_update(self, data_type):
        """
        해당 데이터가 지금 갱신되어야 하는지 확인합니다.
        """

        current_time = time.time()

        last_time = self.last_update.get(data_type)

        # 한 번도 조회하지 않았다면 즉시 조회
        if last_time is None:
            return True

        interval = self.intervals[data_type]

        return (current_time - last_time) >= interval

    def mark_updated(self, data_type):
        """
        해당 데이터가 갱신되었음을 기록합니다.
        """

        self.last_update[data_type] = time.time()

if __name__ == "__main__":

    manager = DataManager()

    print("📊 데이터 갱신 주기 테스트")
    print()

    for data_type, interval in manager.intervals.items():
        print(f"{data_type:<15} : {interval}초")

    print()
    print("주가 갱신 필요:", manager.should_update("stock_price"))

    manager.mark_updated("stock_price")

    print("주가 갱신 필요:", manager.should_update("stock_price"))