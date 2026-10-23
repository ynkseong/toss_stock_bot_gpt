"""
SOXL / SOXS / TQQQ / SQQQ 균등 배분 익절 시뮬레이터 (순수 로직 - UI 의존 없음)

규칙
  1) 시작 시 자금을 4종목에 균등(각 25%) 배분해 현재가로 최대한 매수 (정수 주 단위, 남는 돈은 현금)
  2) 각 종목은 '평균단가 대비 +목표 수익률(기본 5%)'에 도달했을 때만 전량 매도
     (손실 구간에서는 절대 매도하지 않음)
  3) 매도 후 같은 종목은 REBUY_DELAY_SEC(2분) 동안 현금으로 쉬었다가 현재가로 다시 매수
  4) 최근 1시간(롤링) 동안 매수+매도 합계가 MAX_TRADES_PER_HOUR(10회)를 넘지 않도록 제한
     - 한도에 도달하면 매수/매도 모두 대기하고, 오래된 거래가 1시간을 벗어나면 다시 진행
  5) 수수료는 매도 시에만 SELL_FEE($1 고정)를 차감한 금액이 입금됨 (매수 수수료 없음)

상태는 JSON 파일로 저장되어 프로그램을 껐다 켜도 이어집니다.
실제 주문은 전혀 내지 않으며, 체결가는 '마지막으로 조회된 현재가'로 가정합니다.
"""

import json
import os
import time
from datetime import datetime

SYMBOLS = ("SOXL", "SOXS", "TQQQ", "SQQQ")

REBUY_DELAY_SEC = 120        # 매도 후 재매수까지 대기 시간 (2분)
MAX_TRADES_PER_HOUR = 10     # 1시간(롤링) 최대 거래 횟수 (매수 + 매도)
SELL_FEE = 1.0               # 매도 1회당 고정 수수료 ($)
WINDOW_SEC = 3600


def _fmt(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def _new_state():
    return {
        "started": False,
        "started_at": None,
        "initial_cash": 40000.0,
        "take_profit_pct": 5.0,
        "reinvest": True,
        "rebuy_delay_sec": REBUY_DELAY_SEC,
        "max_trades_per_hour": MAX_TRADES_PER_HOUR,
        "sell_fee": SELL_FEE,
        "realized_pnl": 0.0,
        "total_fees": 0.0,
        "slots": {s: {"cash": 0.0, "shares": 0, "avg": 0.0, "rebuy_at": None} for s in SYMBOLS},
        "trades": [],
    }


class SoxSimulator:

    def __init__(self, state_path=None):
        self.state_path = state_path
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
                    # 종목 구성이 다른 이전 버전 저장 파일: 지우지 않고 백업해 두고 새로 시작
                    try:
                        os.replace(self.state_path, self.state_path + ".bak")
                    except OSError:
                        pass
                    return None
                base["slots"][s].setdefault("rebuy_at", None)  # 이전 버전 저장 파일 호환
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
    # 거래 횟수 제한 (최근 1시간 롤링)
    # --------------------------------------------------------

    def trades_in_window(self, now=None):
        now = time.time() if now is None else now
        return sum(1 for t in self.state["trades"] if t.get("ts", 0) > now - WINDOW_SEC)

    def _can_trade(self, now):
        return self.trades_in_window(now) < self.state["max_trades_per_hour"]

    # --------------------------------------------------------
    # 시작 / 초기화
    # --------------------------------------------------------

    @property
    def started(self):
        return self.state["started"]

    def start(self, prices, initial_cash, take_profit_pct, reinvest=True, now=None):
        now = time.time() if now is None else now

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
            if (initial_cash / len(SYMBOLS)) < p:
                raise ValueError(
                    f"{s} 1주 가격(${p:,.2f})보다 배분 금액(${initial_cash / len(SYMBOLS):,.2f})이 작아 매수할 수 없습니다."
                )

        self.state = _new_state()
        self.state.update(
            started=True,
            started_at=_fmt(now),
            initial_cash=float(initial_cash),
            take_profit_pct=float(take_profit_pct),
            reinvest=bool(reinvest),
        )
        for s in SYMBOLS:
            self.state["slots"][s]["cash"] = float(initial_cash) / len(SYMBOLS)

        events = [self._buy(s, prices[s], now) for s in SYMBOLS]  # 최초 매수는 횟수 제한과 무관
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

    def _buy(self, sym, price, now):
        slot = self.state["slots"][sym]
        shares = int(slot["cash"] // price)  # 매수 수수료 없음
        if shares <= 0:
            return None
        cost = shares * price
        slot["cash"] -= cost
        slot["shares"] = shares
        slot["avg"] = price
        slot["rebuy_at"] = None
        return self._record(now, sym, "BUY", shares, price, None, 0.0)

    def _sell(self, sym, price, now):
        slot = self.state["slots"][sym]
        shares = slot["shares"]
        fee = float(self.state["sell_fee"])
        gross = shares * price
        proceeds = gross - fee                     # 수수료를 뺀 금액이 입금됨
        pnl = proceeds - shares * slot["avg"]      # 수수료 반영 실현손익
        slot["cash"] += proceeds
        slot["shares"] = 0
        slot["avg"] = 0.0
        slot["rebuy_at"] = (now + self.state["rebuy_delay_sec"]) if self.state["reinvest"] else None
        self.state["realized_pnl"] += pnl
        self.state["total_fees"] += fee
        return self._record(now, sym, "SELL", shares, price, pnl, fee)

    def _record(self, now, sym, side, shares, price, pnl, fee):
        event = {
            "ts": now,
            "time": _fmt(now),
            "symbol": sym,
            "side": side,
            "shares": shares,
            "price": price,
            "pnl": pnl,
            "fee": fee,
        }
        self.state["trades"].append(event)
        return event

    # --------------------------------------------------------
    # 시세가 들어올 때마다 호출
    # --------------------------------------------------------

    def on_prices(self, prices, now=None):
        """새 시세로 익절/재매수 조건을 검사하고, 발생한 체결 이벤트 리스트를 반환."""
        if not self.started:
            return []

        now = time.time() if now is None else now
        events = []
        target = self.state["take_profit_pct"]

        for sym in SYMBOLS:
            price = prices.get(sym)
            if not price or price <= 0:
                continue

            slot = self.state["slots"][sym]

            if slot["shares"] > 0:
                gain_pct = (price / slot["avg"] - 1) * 100
                if gain_pct >= target and self._can_trade(now):
                    events.append(self._sell(sym, price, now))

            elif self.state["reinvest"]:
                due = slot["rebuy_at"] is None or now >= slot["rebuy_at"]
                if due and self._can_trade(now):
                    ev = self._buy(sym, price, now)
                    if ev:
                        events.append(ev)

        if events:
            self._save()
        return events

    # --------------------------------------------------------
    # 화면 표시용 요약
    # --------------------------------------------------------

    def snapshot(self, prices, now=None):
        now = time.time() if now is None else now
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

            rebuy_in = None
            if shares == 0 and slot.get("rebuy_at"):
                rebuy_in = max(0, int(slot["rebuy_at"] - now))

            positions.append({
                "symbol": sym,
                "shares": shares,
                "avg": avg,
                "price": price,
                "pnl_pct": ((price / avg - 1) * 100) if (shares and price and avg) else None,
                "target_price": avg * (1 + st["take_profit_pct"] / 100) if shares else None,
                "value": value,
                "slot_cash": slot["cash"],
                "rebuy_in": rebuy_in,
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
            "total_fees": st["total_fees"],
            "trades_last_hour": self.trades_in_window(now),
            "max_trades_per_hour": st["max_trades_per_hour"],
            "positions": positions,
            "trades": list(reversed(st["trades"])),  # 최신순
        }
