# ==========================================
# 조건 판단 엔진
# 앞으로 조건(뉴스, SNS 발언, 매크로 지표 등)을
# 하나씩 이 파일에 함수로 추가해나갑니다.
# ==========================================

# 반도체 관련 종목 (SOX 조건을 적용할 대상)
SEMICONDUCTOR_SYMBOLS = {"000660", "NVDA", "INTC", "SNDK", "MU", "AMD"}


def check_sox_condition(sox_condition):
    """
    조건 1: SOX 지수가 전일 대비 상승했는가
    """
    if sox_condition is None:
        return "UNKNOWN"

    return "BUY" if sox_condition["is_up"] else "HOLD"


def evaluate_symbol(symbol, sox_condition):
    """
    종목별 최종 시그널 판단.
    지금은 반도체 종목에 대해서만 SOX 조건을 적용합니다.
    이후 조건이 늘어나면 여기서 여러 조건을 조합하면 됩니다.
    """
    if symbol not in SEMICONDUCTOR_SYMBOLS:
        return "HOLD"

    return check_sox_condition(sox_condition)