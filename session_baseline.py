"""
장 시작 기준가(정규장 시가) 관리 - 누적 변화 / 누적 변화율 계산용

기준가 = 그날 정규장의 시가(첫 1분봉 시가).
  1순위: Yahoo chart API(1분봉)의 첫 시가  → 프로그램을 장중에 켜도 정확한 시가를 알 수 있음
  2순위: Yahoo 조회 실패 시, 프로그램이 장중에 처음 본 가격 ('observed')
         (이후 Yahoo 조회가 성공하면 자동으로 정확한 시가로 교체됨)

장이 끝난 뒤에는 그날의 기준가를 그대로 유지하므로, 마감 시점의 '하루 누적 변화'가 계속 표시되고
다음 장이 시작되면 자동으로 새 기준가로 바뀝니다.
"""

import threading
import time
from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo

import requests

KR_TZ = ZoneInfo("Asia/Seoul")
US_TZ = ZoneInfo("America/New_York")

_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"


def is_kr_symbol(symbol):
    """한국 종목코드(숫자로 시작)인지 여부"""
    return symbol[:1].isdigit()


def market_open_flags(now_kr=None, now_us=None):
    """(한국장 열림, 미국장 열림). 주말만 반영하고 공휴일은 반영하지 않습니다."""
    now_kr = now_kr or datetime.now(KR_TZ)
    now_us = now_us or datetime.now(US_TZ)
    kr_open = now_kr.weekday() < 5 and dt_time(9, 0) <= now_kr.time() < dt_time(15, 30)
    us_open = now_us.weekday() < 5 and dt_time(9, 30) <= now_us.time() < dt_time(16, 0)
    return kr_open, us_open


class SessionBaseline:

    RETRY_SECONDS = 60  # 같은 종목의 Yahoo 재조회 최소 간격

    def __init__(self):
        self._lock = threading.Lock()
        self._base = {}       # symbol -> {"session", "price", "source", "provisional"}
        self._last_try = {}   # symbol -> 마지막 Yahoo 조회 시각
        self._http = requests.Session()
        self._http.headers.update({"User-Agent": "Mozilla/5.0"})

    # --------------------------------------------------------
    # 화면(메인 스레드)에서 사용
    # --------------------------------------------------------

    def get(self, symbol):
        """기준가를 반환. 아직 없으면 None."""
        with self._lock:
            base = self._base.get(symbol)
            return base["price"] if base else None

    def source(self, symbol):
        with self._lock:
            base = self._base.get(symbol)
            return base["source"] if base else None

    # --------------------------------------------------------
    # 시세 조회 스레드에서 호출 (네트워크 사용 가능)
    # --------------------------------------------------------

    def ensure(self, prices, kr_open, us_open):
        """
        prices: {symbol: 현재가}
        필요한 종목에 대해서만 기준가를 새로 구하므로 평소에는 네트워크를 쓰지 않습니다.
        """
        now = time.time()

        for sym, price in prices.items():
            if not price or price <= 0:
                continue

            kr = is_kr_symbol(sym)
            open_now = kr_open if kr else us_open
            tz = KR_TZ if kr else US_TZ
            today = datetime.now(tz).strftime("%Y-%m-%d")

            with self._lock:
                base = dict(self._base[sym]) if sym in self._base else None

            # 새로 구해야 하는가?
            stale = (
                base is None
                or (open_now and (base["session"] != today or base["provisional"]))
            )
            upgradable = bool(open_now and base and base["source"] == "observed")

            if (stale or upgradable) and now - self._last_try.get(sym, 0) >= self.RETRY_SECONDS:
                self._last_try[sym] = now
                found = self._fetch_open(sym, kr, today if open_now else None)
                if found:
                    self._set(sym, found["session"], found["price"], "yahoo", False)
                    continue

            # Yahoo 실패 시 대체 기준가 (현재 가격 기준)
            if stale:
                if open_now:
                    self._set(sym, today, price, "observed", False)
                elif base is None:
                    # 장이 닫혀 있고 아무 정보도 없는 경우: 임시값(장이 열리면 교체됨)
                    self._set(sym, today, price, "observed", True)

    def _set(self, sym, session, price, source, provisional):
        with self._lock:
            self._base[sym] = {
                "session": session,
                "price": float(price),
                "source": source,
                "provisional": provisional,
            }

    # --------------------------------------------------------
    # Yahoo 1분봉에서 정규장 첫 시가 구하기
    # --------------------------------------------------------

    def _fetch_open(self, sym, kr, expect_session):
        tickers = [f"{sym}.KS", f"{sym}.KQ"] if kr else [sym]

        for ticker in tickers:
            try:
                r = self._http.get(
                    _CHART_URL.format(ticker=ticker),
                    params={"range": "1d", "interval": "1m"},
                    timeout=8,
                )
                if r.status_code != 200:
                    continue

                result = (r.json().get("chart", {}).get("result") or [None])[0]
                if not result:
                    continue

                tz_name = result.get("meta", {}).get("exchangeTimezoneName")
                tz = ZoneInfo(tz_name) if tz_name else (KR_TZ if kr else US_TZ)
                timestamps = result.get("timestamp") or []
                opens = (result.get("indicators", {}).get("quote") or [{}])[0].get("open") or []

                for ts, o in zip(timestamps, opens):
                    if o is None or o <= 0:
                        continue
                    session = datetime.fromtimestamp(ts, tz).strftime("%Y-%m-%d")
                    # 장중인데 아직 오늘 봉이 안 올라온 경우(데이터 지연)는 사용하지 않음
                    if expect_session and session != expect_session:
                        return None
                    return {"session": session, "price": float(o)}
            except Exception:
                continue

        return None
