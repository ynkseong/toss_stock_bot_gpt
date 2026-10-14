"""
SOXL / SOXS 50:50 익절 시뮬레이터 (순수 로직 - UI 의존 없음)

규칙
  1) 시작 시 자금을 SOXL / SOXS에 50%씩 배분해 현재가로 매수 (정수 주 단위, 남는 돈은 현금)
  2) 각 종목은 '평균단가 대비 +목표 수익률(기본 5%)'에 도달했을 때만 전량 매도
     (손실 구간에서는 절대 매도하지 않음)
  3) 매도 후 같은 종목 슬롯의 자금으로 즉시 재매수 (reinvest=True 일 때)

상태는 JSON 파일로 저장되어 프로그램을 껐다 켜도 이어집니다.
실제 주문은 전혀 내지 않으며, 체결가는 '마지막으로 조회된 현재가'로 가정합니다.
"""

import json
import os
from datetime import datetime

SYMBOLS = ("SOXL", "SOXS")


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _new_state():
    return {
        "started": False,
        "started_at": None,
        "initial_cash": 1000.0,
        "take_profit_pct": 5.0,
        "reinvest": True,
        "realized_pnl": 0.0,
        "slots": {s: {"cash": 0.0, "shares": 0, "avg": 0.0} for s in SYMBOLS},
        "trades": [],
    }


class SoxSimulator:

    def __init__(self, state_path=None, fee_rate=0.0):
        self.state_path = state_path
        self.fee_rate = fee_rate  # 매수/매도 각각에 적용되는 수수료율 (0.001 = 0.1%)
        self.state = self._load() or _new_state()

    # --------------------------------------------------------
    # 저장 / 불러오기
    # --------------------------------------------------------

    def _load(self):
        if not self.state_path or not os.path.exists(self.state_path):
            return None
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            base = _new_state()
            base.update(data)
            for s in SYMBOLS:
                if s not in base["slots"]:
                    return None
            return base
        except Exception as e:
            print("⚠️ 시뮬레이션 상태 불러오기 실패:", e)
            return None

    def _save(self):
        if not self.state_path:
            return
        tmp = self.state_path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.state_path)  # 쓰다가 꺼져도 기존 파일이 깨지지 않도록
        except Exception as e:
            print("⚠️ 시뮬레이션 상태 저장 실패:", e)

    # --------------------------------------------------------
    # 시작 / 초기화
    # --------------------------------------------------------

    @property
    def started(self):
        return self.state["started"]

    def start(self, prices, initial_cash, take_profit_pct, reinvest=True):
        if self.started:
            raise ValueError("이미 시뮬레이션이 진행 중입니다. 초기화 후 다시 시작하세요.")
        if initial_cash <= 0 or take_profit_pct <= 0:
            raise ValueError("초기 자금과 목표 수익률은 0보다 커야 합니다.")

        for s in SYMBOLS:
            p = prices.get(s)
            if not p or p <= 0:
                raise ValueError(
                    f"{s} 시세를 아직 받지 못했습니다.\n주가 업데이트가 한 번 끝난 뒤 다시 시작하세요."
                )
            if (initial_cash / 2) < p * (1 + self.fee_rate):
                raise ValueError(
                    f"{s} 1주 가격(${p:,.2f})보다 배분 금액(${initial_cash / 2:,.2f})이 작아 매수할 수 없습니다."
                )

        self.state = _new_state()
        self.state.update(
            started=True,
            started_at=_now(),
            initial_cash=float(initial_cash),
            take_profit_pct=float(take_profit_pct),
            reinvest=bool(reinvest),
        )
        for s in SYMBOLS:
            self.state["slots"][s]["cash"] = float(initial_cash) / 2

        ts = _now()
        events = [self._buy(s, prices[s], ts) for s in SYMBOLS]
        self._save()
        return [e for e in events if e]

    def reset(self):
        self.state = _new_state()
        if self.state_path and os.path.exists(self.state_path):
            try:
                os.remove(self.state_path)
            except OSError as e:
                print("⚠️ 상태 파일 삭제 실패:", e)

    # --------------------------------------------------------
    # 매수 / 매도
    # --------------------------------------------------------

    def _buy(self, sym, price, ts):
        slot = self.state["slots"][sym]
        shares = int(slot["cash"] // (price * (1 + self.fee_rate)))
        if shares <= 0:
            return None
        cost = shares * price * (1 + self.fee_rate)
        slot["cash"] -= cost
        slot["shares"] = shares
        slot["avg"] = cost / shares  # 수수료 포함 평단
        return self._record(ts, sym, "BUY", shares, price, None)

    def _sell(self, sym, price, ts):
        slot = self.state["slots"][sym]
        shares = slot["shares"]
        proceeds = shares * price * (1 - self.fee_rate)
        pnl = proceeds - shares * slot["avg"]
        slot["cash"] += proceeds
        slot["shares"] = 0
        slot["avg"] = 0.0
        self.state["realized_pnl"] += pnl
        return self._record(ts, sym, "SELL", shares, price, pnl)

    def _record(self, ts, sym, side, shares, price, pnl):
        event = {
            "time": ts,
            "symbol": sym,
            "side": side,
            "shares": shares,
            "price": price,
            "pnl": pnl,
        }
        self.state["trades"].append(event)
        return event

    # --------------------------------------------------------
    # 시세가 들어올 때마다 호출
    # --------------------------------------------------------

    def on_prices(self, prices):
        """새 시세로 익절 조건을 검사하고, 발생한 체결 이벤트 리스트를 반환."""
        if not self.started:
            return []

        events = []
        ts = _now()
        target = self.state["take_profit_pct"]

        for sym in SYMBOLS:
            price = prices.get(sym)
            if not price or price <= 0:
                continue

            slot = self.state["slots"][sym]

            if slot["shares"] > 0:
                gain_pct = (price / slot["avg"] - 1) * 100
                if gain_pct >= target:
                    events.append(self._sell(sym, price, ts))
                    if self.state["reinvest"]:
                        ev = self._buy(sym, price, ts)
                        if ev:
                            events.append(ev)
            elif self.state["reinvest"]:
                ev = self._buy(sym, price, ts)  # 이전에 자금 부족으로 못 샀던 경우 재시도
                if ev:
                    events.append(ev)

        if events:
            self._save()
        return events

    # --------------------------------------------------------
    # 화면 표시용 요약
    # --------------------------------------------------------

    def snapshot(self, prices):
        st = self.state
        positions = []
        total_cash = 0.0
        total_value = 0.0

        for sym in SYMBOLS:
            slot = st["slots"][sym]
            price = prices.get(sym)
            shares = slot["shares"]
            avg = slot["avg"]

            ref_price = price if price else (avg if shares else 0.0)
            value = shares * ref_price

            total_cash += slot["cash"]
            total_value += value

            positions.append({
                "symbol": sym,
                "shares": shares,
                "avg": avg,
                "price": price,
                "pnl_pct": ((price / avg - 1) * 100) if (shares and price and avg) else None,
                "target_price": avg * (1 + st["take_profit_pct"] / 100) if shares else None,
                "value": value,
                "slot_cash": slot["cash"],
            })

        equity = total_cash + total_value
        initial = st["initial_cash"]
        return {
            "started": st["started"],
            "started_at": st["started_at"],
            "initial_cash": initial,
            "take_profit_pct": st["take_profit_pct"],
            "reinvest": st["reinvest"],
            "cash": total_cash,
            "equity": equity if st["started"] else initial,
            "return_pct": ((equity / initial - 1) * 100) if st["started"] and initial else 0.0,
            "realized_pnl": st["realized_pnl"],
            "positions": positions,
            "trades": list(reversed(st["trades"])),  # 최신순
        }
