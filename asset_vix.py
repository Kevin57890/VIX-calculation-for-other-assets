#!/usr/bin/env python3
"""Compute a 30-day option-implied volatility measure from MarketData.app.

The variance calculation follows the public SPX VIX formula structure:
forward from put-call parity, K0 selection, out-of-the-money option selection,
single-term variance, and 30-day variance interpolation.
"""

from __future__ import annotations

import argparse
from collections import deque
import csv
import datetime as dt
import json
import math
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python 3.8 fallback is not expected here.
    ZoneInfo = None  # type: ignore


MARKETDATA_BASE = "https://api.marketdata.app/v1"
VERSION = "1.5.0"
TREASURY_XML = (
    "https://home.treasury.gov/resource-center/data-chart-center/"
    "interest-rates/pages/xml"
)
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ENV_PATH = os.path.join(APP_DIR, ".env")
DEFAULT_UNIVERSE_PATH = os.path.join(APP_DIR, "universes.csv")
DEFAULT_RECORDS_PATH = os.path.join(APP_DIR, "records", "calculations.csv")
ET_ZONE = ZoneInfo("America/New_York") if ZoneInfo else dt.timezone.utc
UTC = dt.timezone.utc
MINUTES_IN_YEAR = 365 * 24 * 60
MAX_SYMBOL_LENGTH = 16
SYMBOL_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*(?:[.-][A-Z0-9]+)*$")
CSV_FORMULA_PREFIXES = ("=", "+", "-", "@")
CSV_CONTROL_PREFIXES = ("\t", "\r")
_TREASURY_CURVE_CACHE: Dict[dt.date, Tuple[str, Dict[float, float]]] = {}
_CSV_LOCK = threading.RLock()


class AssetVixError(Exception):
    """A clean, user-facing calculation or data error."""


class MarketDataNoContent(AssetVixError):
    """MarketData.app returned a cache miss / no content response."""


@dataclass
class ExpiryChoice:
    expiration: str
    expiry_dt: dt.datetime
    minutes: float
    years: float


@dataclass
class OptionQuote:
    symbol: str
    side: str
    strike: float
    bid: float
    ask: float
    mid: float
    updated: Optional[int]
    volume: Optional[float]
    open_interest: Optional[float]
    underlying_price: Optional[float]


@dataclass
class TermVariance:
    expiration: str
    days: float
    years: float
    rate: float
    forward: float
    k0: float
    variance: float
    strike_count: int
    put_count: int
    call_count: int
    max_quote_age_seconds: Optional[float]


def _to_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, str) and value.lower() in {"nan", "null", "none"}:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _to_int(value: Any) -> Optional[int]:
    number = _to_float(value)
    if number is None:
        return None
    return int(number)


def _to_unix_seconds(value: Any) -> Optional[int]:
    number = _to_float(value)
    if number is None:
        return None
    magnitude = abs(number)
    if magnitude >= 100_000_000_000_000_000:
        number /= 1_000_000_000
    elif magnitude >= 100_000_000_000_000:
        number /= 1_000_000
    elif magnitude >= 100_000_000_000:
        number /= 1_000
    return int(number)


def normalize_symbol(value: Any) -> str:
    symbol = str(value or "").strip().upper()
    if symbol.startswith("$"):
        symbol = symbol[1:]
    return symbol


def symbol_format_error(symbol: str) -> str:
    if not symbol:
        return "symbol is empty"
    if len(symbol) > MAX_SYMBOL_LENGTH:
        return f"symbol is longer than {MAX_SYMBOL_LENGTH} characters"
    if not SYMBOL_PATTERN.fullmatch(symbol):
        return "use letters, digits, periods, or hyphens with no path characters"
    return ""


def validate_symbol(value: Any) -> str:
    symbol = normalize_symbol(value)
    reason = symbol_format_error(symbol)
    if reason:
        display = re.sub(r"\s+", " ", str(value or "").strip())[:40] or "(empty)"
        raise AssetVixError(f"Invalid symbol '{display}': {reason}")
    return symbol


def marketdata_symbol_path(value: Any) -> str:
    return urllib.parse.quote(validate_symbol(value), safe="")


def read_dotenv_value(path: str, key: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            env_key, value = line.split("=", 1)
            if env_key.strip() == key:
                return value.strip().strip('"').strip("'") or None
    return None


def default_marketdata_token() -> Optional[str]:
    return os.getenv("MARKETDATA_TOKEN") or read_dotenv_value(
        DEFAULT_ENV_PATH, "MARKETDATA_TOKEN"
    )


def summarize_marketdata_error(detail: str) -> str:
    try:
        payload = json.loads(detail)
    except json.JSONDecodeError:
        payload = {}

    message = payload.get("errmsg") if isinstance(payload, dict) else None
    if not message and isinstance(payload, dict):
        title = payload.get("title")
        detail_text = payload.get("detail")
        if title and detail_text:
            message = f"{title}: {detail_text}"
        elif title:
            message = str(title)
        elif detail_text:
            message = str(detail_text)
    if not message:
        message = detail.strip()
    message = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", "[ip]", message)
    message = re.sub(r"\s+", " ", message)
    return message[:300] or "MarketData request failed"


def marketdata_get(
    path: str,
    params: Dict[str, Any],
    token: str,
    timeout: int = 30,
    retries: int = 2,
    retry_delay: float = 1.0,
) -> Tuple[Dict[str, Any], int]:
    query = urllib.parse.urlencode(
        {k: v for k, v in params.items() if v is not None}
    )
    url = f"{MARKETDATA_BASE}{path}"
    if query:
        url = f"{url}?{query}"

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "AssetVIX/1.0",
        },
    )

    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = response.status
                if status == 204:
                    raise MarketDataNoContent("MarketData cache miss: 204 No Content")
                body = response.read().decode("utf-8")
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 204:
                raise MarketDataNoContent(
                    "MarketData cache miss: 204 No Content"
                ) from exc
            detail = exc.read().decode("utf-8", errors="replace")
            if (
                exc.code in {429, 500, 502, 503, 504}
                or 520 <= exc.code <= 530
            ) and attempt < retries:
                time.sleep(retry_delay * (attempt + 1))
                continue
            summary = summarize_marketdata_error(detail)
            raise AssetVixError(f"MarketData HTTP {exc.code}: {summary}") from exc
        except urllib.error.URLError as exc:
            if attempt < retries:
                time.sleep(retry_delay * (attempt + 1))
                continue
            raise AssetVixError(f"MarketData request failed: {exc}") from exc
    else:  # pragma: no cover - loop always breaks or raises.
        raise AssetVixError("MarketData request failed")

    if status not in (200, 203):
        raise AssetVixError(f"Unexpected MarketData status code: {status}")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise AssetVixError("MarketData returned non-JSON content") from exc
    if not isinstance(payload, dict):
        raise AssetVixError("MarketData returned an unexpected JSON structure")

    if payload.get("s") == "error":
        raise AssetVixError(payload.get("errmsg", "MarketData returned an error"))
    if payload.get("s") == "no_data":
        raise AssetVixError(payload.get("errmsg", "MarketData returned no data"))
    return payload, status


def get_expirations(symbol: str, token: str, mode: Optional[str]) -> List[str]:
    params = {"mode": mode} if mode else {}
    symbol_path = marketdata_symbol_path(symbol)
    payload, _ = marketdata_get(f"/options/expirations/{symbol_path}/", params, token)
    expirations = payload.get("expirations")
    if not isinstance(expirations, list) or not expirations:
        raise AssetVixError("No option expirations returned")
    return [str(exp) for exp in expirations]


def get_chain(
    symbol: str,
    expiration: str,
    token: str,
    mode: str,
    maxage: Optional[str],
    strike_limit: Optional[int],
    min_open_interest: Optional[int],
    min_volume: Optional[int],
    fallback_mode: Optional[str],
    max_bid_ask_spread_pct: Optional[float],
) -> Tuple[List[OptionQuote], int]:
    symbol_path = marketdata_symbol_path(symbol)
    params = {
        "expiration": expiration,
        "mode": mode,
        "maxage": maxage if mode == "cached" else None,
        "strikeLimit": strike_limit,
        "minOpenInterest": min_open_interest,
        "minVolume": min_volume,
        "nonstandard": "false",
    }

    try:
        payload, status = marketdata_get(
            f"/options/chain/{symbol_path}/", params, token
        )
    except MarketDataNoContent:
        if not fallback_mode:
            raise
        params["mode"] = fallback_mode
        params["maxage"] = None
        payload, status = marketdata_get(
            f"/options/chain/{symbol_path}/", params, token
        )

    return chain_payload_to_quotes(payload, max_bid_ask_spread_pct), status


def _array_value(payload: Dict[str, Any], key: str, index: int) -> Any:
    values = payload.get(key)
    if not isinstance(values, list) or index >= len(values):
        return None
    return values[index]


def chain_payload_to_quotes(
    payload: Dict[str, Any],
    max_bid_ask_spread_pct: Optional[float] = None,
) -> List[OptionQuote]:
    symbols = payload.get("optionSymbol")
    if not isinstance(symbols, list):
        raise AssetVixError("Option chain response does not include optionSymbol[]")

    quotes: List[OptionQuote] = []
    for i, option_symbol in enumerate(symbols):
        side = str(_array_value(payload, "side", i) or "").lower()
        strike = _to_float(_array_value(payload, "strike", i))
        bid = _to_float(_array_value(payload, "bid", i))
        ask = _to_float(_array_value(payload, "ask", i))
        mid = _to_float(_array_value(payload, "mid", i))
        if mid is None and bid is not None and ask is not None:
            mid = (bid + ask) / 2

        if side not in {"call", "put"}:
            continue
        if strike is None or bid is None or ask is None or mid is None:
            continue
        if bid < 0 or ask < 0 or ask < bid or mid <= 0:
            continue
        if max_bid_ask_spread_pct is not None and bid > 0:
            spread_pct = ((ask - bid) / mid) * 100
            if spread_pct > max_bid_ask_spread_pct:
                continue

        quotes.append(
            OptionQuote(
                symbol=str(option_symbol),
                side=side,
                strike=strike,
                bid=bid,
                ask=ask,
                mid=mid,
                updated=_to_unix_seconds(_array_value(payload, "updated", i)),
                volume=_to_float(_array_value(payload, "volume", i)),
                open_interest=_to_float(_array_value(payload, "openInterest", i)),
                underlying_price=_to_float(_array_value(payload, "underlyingPrice", i)),
            )
        )

    if not quotes:
        raise AssetVixError("No usable bid/ask quotes in option chain")
    return quotes


def parse_expiry_datetime(
    expiration: str,
    settlement_hour: int,
    settlement_minute: int,
) -> dt.datetime:
    expiry_date = dt.date.fromisoformat(expiration[:10])
    return dt.datetime(
        expiry_date.year,
        expiry_date.month,
        expiry_date.day,
        settlement_hour,
        settlement_minute,
        tzinfo=ET_ZONE,
    )


def choose_expirations(
    expirations: Sequence[str],
    now_et: dt.datetime,
    target_days: float,
    min_days: float,
    max_days: float,
    settlement_hour: int,
    settlement_minute: int,
    allow_extrapolation: bool,
) -> List[ExpiryChoice]:
    target_minutes = target_days * 24 * 60
    choices: List[ExpiryChoice] = []
    for expiration in expirations:
        try:
            expiry_dt = parse_expiry_datetime(
                expiration, settlement_hour, settlement_minute
            )
        except ValueError:
            continue
        minutes = (expiry_dt - now_et).total_seconds() / 60
        days = minutes / (24 * 60)
        if minutes <= 0 or days < min_days or days > max_days:
            continue
        choices.append(
            ExpiryChoice(
                expiration=expiration,
                expiry_dt=expiry_dt,
                minutes=minutes,
                years=minutes / MINUTES_IN_YEAR,
            )
        )

    if not choices:
        raise AssetVixError(
            f"No expirations between {min_days:g} and {max_days:g} days"
        )

    choices.sort(key=lambda item: item.minutes)
    exact = [item for item in choices if abs(item.minutes - target_minutes) < 1]
    if exact:
        return [exact[0]]

    below = [item for item in choices if item.minutes < target_minutes]
    above = [item for item in choices if item.minutes > target_minutes]
    if below and above:
        return [below[-1], above[0]]

    if allow_extrapolation and len(choices) >= 2:
        nearest = sorted(choices, key=lambda item: abs(item.minutes - target_minutes))
        return sorted(nearest[:2], key=lambda item: item.minutes)

    raise AssetVixError(
        "Need two expirations bracketing the target horizon; "
        "use --allow-extrapolation only for exploratory runs"
    )


def fetch_treasury_curve(as_of: dt.date) -> Tuple[str, Dict[float, float]]:
    cached = _TREASURY_CURVE_CACHE.get(as_of)
    if cached is not None:
        return cached

    for year in (as_of.year, as_of.year - 1):
        params = urllib.parse.urlencode(
            {
                "data": "daily_treasury_yield_curve",
                "field_tdr_date_value": str(year),
            }
        )
        url = f"{TREASURY_XML}?{params}"
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                xml_body = response.read()
        except urllib.error.URLError:
            continue

        records = parse_treasury_xml(xml_body)
        records = [(date, curve) for date, curve in records if date <= as_of]
        if records:
            date, curve = records[-1]
            result = (date.isoformat(), curve)
            _TREASURY_CURVE_CACHE[as_of] = result
            return result

    raise AssetVixError("Could not load Treasury yield curve")


def parse_treasury_xml(xml_body: bytes) -> List[Tuple[dt.date, Dict[float, float]]]:
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "d": "http://schemas.microsoft.com/ado/2007/08/dataservices",
        "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
    }
    maturities = {
        "BC_1MONTH": 1 / 12,
        "BC_1_5MONTH": 1.5 / 12,
        "BC_2MONTH": 2 / 12,
        "BC_3MONTH": 3 / 12,
        "BC_4MONTH": 4 / 12,
        "BC_6MONTH": 6 / 12,
        "BC_1YEAR": 1,
        "BC_2YEAR": 2,
        "BC_3YEAR": 3,
        "BC_5YEAR": 5,
        "BC_7YEAR": 7,
        "BC_10YEAR": 10,
        "BC_20YEAR": 20,
        "BC_30YEAR": 30,
    }
    root = ET.fromstring(xml_body)
    records: List[Tuple[dt.date, Dict[float, float]]] = []

    for entry in root.findall("atom:entry", ns):
        properties = entry.find("atom:content/m:properties", ns)
        if properties is None:
            continue
        date_node = properties.find("d:NEW_DATE", ns)
        if date_node is None or not date_node.text:
            continue
        record_date = dt.datetime.fromisoformat(date_node.text).date()
        curve: Dict[float, float] = {}
        for field, maturity in maturities.items():
            node = properties.find(f"d:{field}", ns)
            rate = _to_float(node.text if node is not None else None)
            if rate is not None:
                curve[maturity] = rate / 100
        if curve:
            records.append((record_date, curve))

    records.sort(key=lambda item: item[0])
    return records


def interpolate_rate(curve: Dict[float, float], years: float) -> float:
    points = sorted(curve.items())
    if not points:
        raise AssetVixError("Treasury curve is empty")
    if years <= points[0][0]:
        return points[0][1]
    if years >= points[-1][0]:
        return points[-1][1]

    for (left_t, left_r), (right_t, right_r) in zip(points, points[1:]):
        if left_t <= years <= right_t:
            weight = (years - left_t) / (right_t - left_t)
            return left_r + weight * (right_r - left_r)
    return points[-1][1]


def by_strike_and_side(
    quotes: Iterable[OptionQuote],
) -> Dict[float, Dict[str, OptionQuote]]:
    grouped: Dict[float, Dict[str, OptionQuote]] = {}
    for quote in quotes:
        grouped.setdefault(quote.strike, {})[quote.side] = quote
    return grouped


def consecutive_nonzero_otm(
    strikes: Sequence[float],
    grouped: Dict[float, Dict[str, OptionQuote]],
    side: str,
) -> List[float]:
    included: List[float] = []
    zero_bid_count = 0
    for strike in strikes:
        quote = grouped.get(strike, {}).get(side)
        if quote is None:
            continue
        if quote.bid <= 0:
            zero_bid_count += 1
            if zero_bid_count >= 2:
                break
            continue
        zero_bid_count = 0
        included.append(strike)
    return included


def delta_k(selected_strikes: Sequence[float], index: int) -> float:
    if len(selected_strikes) < 2:
        raise AssetVixError("At least two strikes are required for delta K")
    if index == 0:
        return selected_strikes[1] - selected_strikes[0]
    if index == len(selected_strikes) - 1:
        return selected_strikes[-1] - selected_strikes[-2]
    return (selected_strikes[index + 1] - selected_strikes[index - 1]) / 2


def vix_term_variance(
    selected_strikes: Sequence[float],
    option_prices: Dict[float, float],
    forward: float,
    k0: float,
    rate: float,
    years_to_expiration: float,
) -> float:
    if years_to_expiration <= 0:
        raise AssetVixError("Time to expiration must be positive")
    if k0 <= 0 or forward <= 0:
        raise AssetVixError("Forward and K0 must be positive")

    discount_growth = math.exp(rate * years_to_expiration)
    contributions = (
        (delta_k(selected_strikes, index) / (strike * strike))
        * discount_growth
        * option_prices[strike]
        for index, strike in enumerate(selected_strikes)
    )
    variance = (
        (2 / years_to_expiration) * math.fsum(contributions)
        - ((forward / k0 - 1) ** 2) / years_to_expiration
    )
    if variance <= 0 or math.isnan(variance) or math.isinf(variance):
        raise AssetVixError(f"Non-positive variance: {variance:g}")
    return variance


def compute_term_variance(
    expiration: ExpiryChoice,
    quotes: List[OptionQuote],
    rate: float,
    min_side_strikes: int,
) -> TermVariance:
    grouped = by_strike_and_side(quotes)
    common_strikes = sorted(
        strike
        for strike, sides in grouped.items()
        if "call" in sides and "put" in sides
    )
    if len(common_strikes) < max(3, min_side_strikes):
        raise AssetVixError("Too few strikes with both call and put quotes")

    forward_strike = min(
        common_strikes,
        key=lambda strike: abs(grouped[strike]["call"].mid - grouped[strike]["put"].mid),
    )
    call_mid = grouped[forward_strike]["call"].mid
    put_mid = grouped[forward_strike]["put"].mid
    forward = forward_strike + math.exp(rate * expiration.years) * (call_mid - put_mid)

    all_strikes = sorted(grouped)
    k0_candidates = [strike for strike in common_strikes if strike <= forward]
    if not k0_candidates:
        raise AssetVixError("No strike at or below forward price")
    k0 = k0_candidates[-1]
    if "call" not in grouped[k0] or "put" not in grouped[k0]:
        raise AssetVixError("K0 does not have both call and put quotes")

    put_walk = [strike for strike in all_strikes if strike < k0]
    put_walk.sort(reverse=True)
    call_walk = [strike for strike in all_strikes if strike > k0]

    puts = consecutive_nonzero_otm(put_walk, grouped, "put")
    calls = consecutive_nonzero_otm(call_walk, grouped, "call")
    if len(puts) < min_side_strikes:
        raise AssetVixError(f"Too few usable OTM puts: {len(puts)}")
    if len(calls) < min_side_strikes:
        raise AssetVixError(f"Too few usable OTM calls: {len(calls)}")

    selected = sorted(puts + [k0] + calls)
    if len(selected) < 3:
        raise AssetVixError("Too few selected strikes for variance calculation")

    prices: Dict[float, float] = {}
    for strike in selected:
        if strike < k0:
            prices[strike] = grouped[strike]["put"].mid
        elif strike > k0:
            prices[strike] = grouped[strike]["call"].mid
        else:
            prices[strike] = (
                grouped[strike]["call"].mid + grouped[strike]["put"].mid
            ) / 2

    variance = vix_term_variance(
        selected_strikes=selected,
        option_prices=prices,
        forward=forward,
        k0=k0,
        rate=rate,
        years_to_expiration=expiration.years,
    )

    updated_values = [quote.updated for quote in quotes if quote.updated is not None]
    max_age = None
    if updated_values:
        now_ts = time.time()
        max_age = max(max(0, now_ts - updated) for updated in updated_values)

    return TermVariance(
        expiration=expiration.expiration,
        days=expiration.minutes / (24 * 60),
        years=expiration.years,
        rate=rate,
        forward=forward,
        k0=k0,
        variance=variance,
        strike_count=len(selected),
        put_count=len(puts),
        call_count=len(calls),
        max_quote_age_seconds=max_age,
    )


def interpolate_variance(
    terms: Sequence[TermVariance],
    target_days: float,
) -> float:
    target_minutes = target_days * 24 * 60
    if len(terms) == 1:
        return terms[0].variance
    if len(terms) != 2:
        raise AssetVixError("Expected one or two term variances")

    front, rear = sorted(terms, key=lambda item: item.years)
    front_minutes = front.years * MINUTES_IN_YEAR
    rear_minutes = rear.years * MINUTES_IN_YEAR
    denominator = rear_minutes - front_minutes
    if denominator <= 0:
        raise AssetVixError("Expiration terms are not ordered correctly")

    sum1 = front.years * front.variance * (rear_minutes - target_minutes) / denominator
    sum2 = rear.years * rear.variance * (target_minutes - front_minutes) / denominator
    interpolated = (sum1 + sum2) * MINUTES_IN_YEAR / target_minutes
    if interpolated <= 0 or math.isnan(interpolated) or math.isinf(interpolated):
        raise AssetVixError(f"Non-positive interpolated variance: {interpolated:g}")
    return interpolated


def max_term_quote_age_seconds(terms: Sequence[TermVariance]) -> Optional[float]:
    ages = [
        term.max_quote_age_seconds
        for term in terms
        if term.max_quote_age_seconds is not None
    ]
    return max(ages) if ages else None


def compute_asset_vix(
    symbol: str,
    token: str,
    mode: str,
    fallback_mode: Optional[str],
    maxage: Optional[str],
    strike_limit: Optional[int],
    min_open_interest: Optional[int],
    min_volume: Optional[int],
    target_days: float,
    min_days: float,
    max_days: float,
    min_side_strikes: int,
    max_quote_age_minutes: Optional[float],
    allow_stale: bool,
    allow_extrapolation: bool,
    settlement_hour: int,
    settlement_minute: int,
    manual_rate: Optional[float],
    max_bid_ask_spread_pct: Optional[float],
) -> Dict[str, Any]:
    symbol = validate_symbol(symbol)
    now_et = dt.datetime.now(ET_ZONE)
    expirations = get_expirations(symbol, token, mode=None)
    selected_expirations = choose_expirations(
        expirations=expirations,
        now_et=now_et,
        target_days=target_days,
        min_days=min_days,
        max_days=max_days,
        settlement_hour=settlement_hour,
        settlement_minute=settlement_minute,
        allow_extrapolation=allow_extrapolation,
    )

    if manual_rate is None:
        curve_date, curve = fetch_treasury_curve(now_et.date())
        rate_source = f"treasury_xml:{curve_date}"
    else:
        curve_date = None
        curve = {}
        rate_source = "manual"

    terms: List[TermVariance] = []
    http_statuses: List[int] = []
    for expiration in selected_expirations:
        rate = manual_rate if manual_rate is not None else interpolate_rate(
            curve, expiration.years
        )
        quotes, status = get_chain(
            symbol=symbol,
            expiration=expiration.expiration,
            token=token,
            mode=mode,
            maxage=maxage,
            strike_limit=strike_limit,
            min_open_interest=min_open_interest,
            min_volume=min_volume,
            fallback_mode=fallback_mode,
            max_bid_ask_spread_pct=max_bid_ask_spread_pct,
        )
        http_statuses.append(status)
        terms.append(
            compute_term_variance(
                expiration=expiration,
                quotes=quotes,
                rate=rate,
                min_side_strikes=min_side_strikes,
            )
        )

    max_age_seconds = max_term_quote_age_seconds(terms)
    stale_reason = ""
    if max_quote_age_minutes is not None and max_age_seconds is not None:
        if max_age_seconds > max_quote_age_minutes * 60:
            stale_reason = (
                f"stale_quotes:max_age_minutes={max_age_seconds / 60:.1f}"
            )
            if not allow_stale:
                raise AssetVixError(stale_reason)

    variance_30d = interpolate_variance(terms, target_days)
    asset_vix = math.sqrt(variance_30d) * 100
    status = "ok" if not stale_reason else stale_reason

    result: Dict[str, Any] = {
        "ts_utc": dt.datetime.now(UTC).isoformat(timespec="seconds"),
        "symbol": symbol,
        "status": status,
        "asset_vix_30d": round(asset_vix, 4),
        "variance_30d": round(variance_30d, 8),
        "target_days": target_days,
        "rate_source": rate_source,
        "mode": mode,
        "http_statuses": ",".join(str(status) for status in http_statuses),
        "expirations": ",".join(term.expiration for term in terms),
        "days": ",".join(f"{term.days:.3f}" for term in terms),
        "rates": ",".join(f"{term.rate:.6f}" for term in terms),
        "forwards": ",".join(f"{term.forward:.4f}" for term in terms),
        "k0": ",".join(f"{term.k0:.4f}" for term in terms),
        "strike_counts": ",".join(str(term.strike_count) for term in terms),
        "put_counts": ",".join(str(term.put_count) for term in terms),
        "call_counts": ",".join(str(term.call_count) for term in terms),
        "max_quote_age_minutes": (
            round(max_age_seconds / 60, 2)
            if max_age_seconds is not None
            else None
        ),
        "reason": "",
    }
    return result


def compute_symbol_safe(symbol: str, args: argparse.Namespace) -> Dict[str, Any]:
    row_symbol = normalize_symbol(symbol)
    try:
        return compute_asset_vix(
            symbol=symbol,
            token=args.token,
            mode=args.mode,
            fallback_mode=args.fallback_mode,
            maxage=args.maxage,
            strike_limit=args.strike_limit,
            min_open_interest=args.min_open_interest,
            min_volume=args.min_volume,
            target_days=args.target_days,
            min_days=args.min_days,
            max_days=args.max_days,
            min_side_strikes=args.min_side_strikes,
            max_quote_age_minutes=args.max_quote_age_minutes,
            allow_stale=args.allow_stale,
            allow_extrapolation=args.allow_extrapolation,
            settlement_hour=args.settlement_hour,
            settlement_minute=args.settlement_minute,
            manual_rate=args.risk_free_rate,
            max_bid_ask_spread_pct=args.max_bid_ask_spread_pct,
        )
    except Exception as exc:  # Keep batch runs alive per symbol.
        return {
            "ts_utc": dt.datetime.now(UTC).isoformat(timespec="seconds"),
            "symbol": row_symbol,
            "status": "error",
            "asset_vix_30d": None,
            "variance_30d": None,
            "target_days": args.target_days,
            "rate_source": "manual" if args.risk_free_rate is not None else "treasury_xml",
            "mode": args.mode,
            "http_statuses": "",
            "expirations": "",
            "days": "",
            "rates": "",
            "forwards": "",
            "k0": "",
            "strike_counts": "",
            "put_counts": "",
            "call_counts": "",
            "max_quote_age_minutes": None,
            "reason": str(exc),
        }


def csv_safe_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.lstrip()
    if value.startswith(CSV_CONTROL_PREFIXES):
        return f"'{value}"
    if stripped.startswith(CSV_FORMULA_PREFIXES):
        return f"'{value}"
    return value


def csv_safe_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {key: csv_safe_value(value) for key, value in row.items()}


def write_csv_rows(path: str, rows: Sequence[Dict[str, Any]]) -> None:
    if not rows:
        return
    safe_rows = [csv_safe_row(row) for row in rows]
    with _CSV_LOCK:
        directory = os.path.dirname(os.path.abspath(path))
        if directory:
            os.makedirs(directory, exist_ok=True)
        exists = os.path.exists(path)
        has_content = exists and os.path.getsize(path) > 0
        fieldnames = list(safe_rows[0].keys())
        if has_content:
            with open(path, "r", newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                existing_fieldnames = reader.fieldnames or []
                old_rows = list(reader)
            if existing_fieldnames and existing_fieldnames != fieldnames:
                merged = list(existing_fieldnames)
                for name in fieldnames:
                    if name not in merged:
                        merged.append(name)
                with open(path, "w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=merged)
                    writer.writeheader()
                    writer.writerows(csv_safe_row(row) for row in old_rows)
                fieldnames = merged
        with open(path, "a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            if not has_content:
                writer.writeheader()
            writer.writerows(safe_rows)


def record_rows(
    path: str,
    rows: Sequence[Dict[str, Any]],
    source: str,
    run_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if not rows:
        return []

    record_id = run_id or uuid.uuid4().hex
    recorded_at = dt.datetime.now(UTC).isoformat(timespec="seconds")
    record_rows = []
    for row in rows:
        enriched = {
            "recorded_at_utc": recorded_at,
            "run_id": record_id,
            "source": source,
        }
        enriched.update(row)
        record_rows.append(enriched)

    write_csv_rows(path, record_rows)
    return record_rows


def read_recent_csv_rows(path: str, limit: int = 50) -> List[Dict[str, str]]:
    if limit <= 0:
        return []
    with _CSV_LOCK:
        if not os.path.isfile(path):
            return []
        with open(path, "r", newline="", encoding="utf-8") as handle:
            return list(deque(csv.DictReader(handle), maxlen=limit))


def read_csv_rows(path: str) -> Tuple[List[str], List[Dict[str, str]]]:
    with _CSV_LOCK:
        if not os.path.isfile(path):
            return [], []
        with open(path, "r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            return list(reader.fieldnames or []), list(reader)


def clear_csv_rows(path: str) -> bool:
    with _CSV_LOCK:
        if not os.path.isfile(path):
            return False
        os.remove(path)
        return True


def print_rows(rows: Sequence[Dict[str, Any]], as_json: bool) -> None:
    if as_json:
        for row in rows:
            print(json.dumps(row, ensure_ascii=False, sort_keys=True))
        return

    columns = [
        "ts_utc",
        "symbol",
        "status",
        "asset_vix_30d",
        "expirations",
        "days",
        "strike_counts",
        "max_quote_age_minutes",
        "reason",
    ]
    widths = {
        column: max(
            len(column),
            *(len(str(row.get(column, ""))) for row in rows),
        )
        for column in columns
    }
    print("  ".join(column.ljust(widths[column]) for column in columns))
    print("  ".join("-" * widths[column] for column in columns))
    for row in rows:
        print("  ".join(str(row.get(column, "")).ljust(widths[column]) for column in columns))


def parse_symbols(value: str) -> List[str]:
    symbols = [normalize_symbol(part) for part in re.split(r"[,;\s]+", value or "")]
    return dedupe_symbols(symbols)


def dedupe_symbols(symbols: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for symbol in symbols:
        cleaned = normalize_symbol(symbol)
        if not cleaned:
            continue
        cleaned = validate_symbol(cleaned)
        if cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def load_symbol_universes(path: str = DEFAULT_UNIVERSE_PATH) -> Dict[str, List[str]]:
    if not os.path.exists(path):
        return {}

    groups: Dict[str, List[str]] = {"all": []}
    with open(path, "r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            symbol = str(row.get("symbol") or "").strip().upper()
            if not symbol:
                continue
            active = str(row.get("active") or "true").strip().lower()
            if active in {"0", "false", "no", "n"}:
                continue
            groups["all"].append(symbol)

            tier = str(row.get("tier") or "").strip().lower()
            if tier:
                groups.setdefault(tier, []).append(symbol)

            group_value = str(row.get("groups") or row.get("group") or "")
            for group in re.split(r"[,;|]+", group_value):
                name = group.strip().lower()
                if name:
                    groups.setdefault(name, []).append(symbol)

    groups["all"] = dedupe_symbols(groups.get("all", []))
    groups["liquid50"] = groups["all"][:50]
    groups["liquid100"] = groups["all"][:100]
    for name, symbols in list(groups.items()):
        groups[name] = dedupe_symbols(symbols)
    return groups


def resolve_symbols(
    symbols_arg: Optional[str],
    universe: Optional[str],
    universe_file: str,
    max_symbols: Optional[int],
) -> List[str]:
    symbols: List[str] = []
    if universe:
        universes = load_symbol_universes(universe_file)
        key = universe.strip().lower()
        if key not in universes:
            available = ", ".join(sorted(universes)) or "none"
            raise AssetVixError(f"Unknown universe '{universe}'. Available: {available}")
        symbols.extend(universes[key])
    if symbols_arg:
        symbols.extend(parse_symbols(symbols_arg))
    symbols = dedupe_symbols(symbols)
    if max_symbols is not None:
        symbols = symbols[:max_symbols]
    return symbols


def compute_symbols(symbols: Sequence[str], args: argparse.Namespace) -> List[Dict[str, Any]]:
    rows = []
    for index, symbol in enumerate(symbols):
        rows.append(compute_symbol_safe(symbol, args))
        delay = getattr(args, "request_delay_seconds", 0) or 0
        if delay > 0 and index < len(symbols) - 1:
            time.sleep(delay)
    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compute 30-day VIX-like implied volatility from MarketData.app."
    )
    parser.add_argument(
        "--symbols",
        default=None,
        help="Comma/newline/space-separated underlying symbols, e.g. SPY,AAPL,NVDA.",
    )
    parser.add_argument(
        "--universe",
        default=None,
        help="Universe name from universes.csv, e.g. core, etfs, mega_cap, liquid50.",
    )
    parser.add_argument(
        "--universe-file",
        default=DEFAULT_UNIVERSE_PATH,
        help="CSV file with symbol,groups,tier,active columns.",
    )
    parser.add_argument(
        "--max-symbols",
        type=int,
        default=None,
        help="Cap the final symbol list after universe + symbols are combined.",
    )
    parser.add_argument(
        "--token",
        default=default_marketdata_token(),
        help="MarketData.app token. Prefer MARKETDATA_TOKEN or asset_vix/.env.",
    )
    parser.add_argument(
        "--mode",
        choices=["live", "cached", "delayed"],
        default="delayed",
        help="MarketData mode. Use cached on paid plans to save credits.",
    )
    parser.add_argument(
        "--fallback-mode",
        choices=["live", "delayed"],
        default=None,
        help="Fallback if mode=cached returns 204. Costs normal credits.",
    )
    parser.add_argument(
        "--maxage",
        default="5min",
        help="Cache age limit used only with --mode cached.",
    )
    parser.add_argument(
        "--strike-limit",
        type=int,
        default=120,
        help="Max strikes per expiration. Increase for SPY/SPX; lower to save credits.",
    )
    parser.add_argument("--min-open-interest", type=int, default=None)
    parser.add_argument("--min-volume", type=int, default=None)
    parser.add_argument(
        "--max-bid-ask-spread-pct",
        type=float,
        default=200.0,
        help="Drop positive-bid quotes wider than this percent of mid; use 0 to disable.",
    )
    parser.add_argument("--target-days", type=float, default=30)
    parser.add_argument("--min-days", type=float, default=23)
    parser.add_argument("--max-days", type=float, default=37)
    parser.add_argument("--min-side-strikes", type=int, default=5)
    parser.add_argument(
        "--max-quote-age-minutes",
        type=float,
        default=45,
        help="Reject stale quotes unless --allow-stale is set.",
    )
    parser.add_argument("--allow-stale", action="store_true")
    parser.add_argument(
        "--allow-extrapolation",
        action="store_true",
        help="Use the nearest two expirations even when they do not bracket 30 days.",
    )
    parser.add_argument("--settlement-hour", type=int, default=16)
    parser.add_argument("--settlement-minute", type=int, default=0)
    parser.add_argument(
        "--risk-free-rate",
        type=float,
        default=None,
        help="Manual annualized decimal rate, e.g. 0.045. Overrides Treasury XML.",
    )
    parser.add_argument(
        "--csv",
        default=DEFAULT_RECORDS_PATH,
        help="Append every calculation to this CSV path.",
    )
    parser.add_argument(
        "--no-record",
        action="store_true",
        help="Do not append calculations to the CSV record file.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON lines.")
    parser.add_argument(
        "--fail-on-non-ok",
        action="store_true",
        help="Exit with status 1 when any symbol result is not ok.",
    )
    parser.add_argument(
        "--request-delay-seconds",
        type=float,
        default=0.25,
        help="Small pause between symbols to reduce bursts and transient API errors.",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Run forever at --interval-seconds cadence.",
    )
    parser.add_argument("--interval-seconds", type=int, default=300)
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def validate_cli_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    finite_values = {
        "--target-days": args.target_days,
        "--min-days": args.min_days,
        "--max-days": args.max_days,
        "--max-bid-ask-spread-pct": args.max_bid_ask_spread_pct,
        "--max-quote-age-minutes": args.max_quote_age_minutes,
        "--request-delay-seconds": args.request_delay_seconds,
        "--risk-free-rate": args.risk_free_rate,
    }
    for option, value in finite_values.items():
        if value is not None and not math.isfinite(value):
            parser.error(f"{option} must be a finite number")

    if args.target_days <= 0:
        parser.error("--target-days must be greater than 0")
    if args.min_days < 0:
        parser.error("--min-days must be at least 0")
    if args.max_days <= args.min_days:
        parser.error("--max-days must be greater than --min-days")
    if args.strike_limit is not None and args.strike_limit < 1:
        parser.error("--strike-limit must be at least 1")
    if args.min_open_interest is not None and args.min_open_interest < 0:
        parser.error("--min-open-interest must be at least 0")
    if args.min_volume is not None and args.min_volume < 0:
        parser.error("--min-volume must be at least 0")
    if args.min_side_strikes < 1:
        parser.error("--min-side-strikes must be at least 1")
    if args.max_quote_age_minutes is not None and args.max_quote_age_minutes < 0:
        parser.error("--max-quote-age-minutes must be at least 0")
    if args.request_delay_seconds < 0:
        parser.error("--request-delay-seconds must be at least 0")
    if args.max_symbols is not None and args.max_symbols < 1:
        parser.error("--max-symbols must be at least 1")
    if args.interval_seconds < 1:
        parser.error("--interval-seconds must be at least 1")
    if not 0 <= args.settlement_hour <= 23:
        parser.error("--settlement-hour must be between 0 and 23")
    if not 0 <= args.settlement_minute <= 59:
        parser.error("--settlement-minute must be between 0 and 59")
    if args.risk_free_rate is not None and not -1 <= args.risk_free_rate <= 1:
        parser.error("--risk-free-rate must be between -1 and 1")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_cli_args(parser, args)
    if args.max_bid_ask_spread_pct is not None and args.max_bid_ask_spread_pct <= 0:
        args.max_bid_ask_spread_pct = None
    if not args.token:
        parser.error(
            "Missing MarketData token. Set MARKETDATA_TOKEN or save asset_vix/.env"
        )

    try:
        symbols = resolve_symbols(
            args.symbols,
            args.universe,
            args.universe_file,
            args.max_symbols,
        )
    except AssetVixError as exc:
        parser.error(str(exc))
    if not symbols:
        symbols = ["SPY"]

    while True:
        rows = compute_symbols(symbols, args)
        print_rows(rows, as_json=args.json)
        if not args.no_record and args.csv:
            record_rows(args.csv, rows, source="cli")
        if args.fail_on_non_ok and any(row.get("status") != "ok" for row in rows):
            return 1
        if not args.watch:
            break
        time.sleep(args.interval_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
