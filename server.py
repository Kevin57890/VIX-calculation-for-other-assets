#!/usr/bin/env python3
"""Local click-to-query web app for AssetVIX."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import math
import mimetypes
import os
import re
import socket
import sys
import threading
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

import asset_vix as calc


APP_DIR = Path(__file__).resolve().parent
WEB_DIR = APP_DIR / "web"
ENV_PATH = APP_DIR / ".env"
RECORDS_PATH = APP_DIR / "records" / "calculations.csv"
UNIVERSE_PATH = APP_DIR / "universes.csv"
MAX_JSON_BODY_BYTES = 64 * 1024
MAX_QUERY_SYMBOLS = 100
_ACTIVE_TOKEN: Optional[str] = None
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
RECORD_HEADERS = [
    "recorded_at_utc",
    "run_id",
    "source",
    "ts_utc",
    "symbol",
    "status",
    "asset_vix_30d",
    "variance_30d",
    "target_days",
    "rate_source",
    "mode",
    "http_statuses",
    "expirations",
    "days",
    "rates",
    "forwards",
    "k0",
    "strike_counts",
    "put_counts",
    "call_counts",
    "max_quote_age_minutes",
    "reason",
]


def mask_token(token: Optional[str]) -> str:
    if not token:
        return ""
    if len(token) <= 8:
        return "configured"
    return f"••••{token[-4:]}"


def normalize_token(raw_token: str) -> str:
    token = raw_token.strip().strip('"').strip("'").strip()
    token = re.sub(r"^authorization\s*:\s*bearer\s+", "", token, flags=re.I)
    token = re.sub(r"^bearer\s+", "", token, flags=re.I)

    assignment = re.search(
        r"(?:marketdata_token|token)\s*=\s*['\"]?([^'\"\s]+)",
        token,
        flags=re.I,
    )
    if assignment:
        token = assignment.group(1)

    label_prefix = re.match(r"^(?:api\s*key|token)\s*[:,]\s*(.+)$", token, flags=re.I)
    if label_prefix:
        token = label_prefix.group(1)

    url_token = re.search(r"[?&]token=([^&\s]+)", token, flags=re.I)
    if url_token:
        token = url_token.group(1)

    token = token.strip().strip("{}").strip().strip('"').strip("'")
    token = re.sub(r"\s+", "", token)
    return token


def token_format_error(token: Optional[str]) -> str:
    if not token:
        return "MarketData token is not configured"
    if len(token) < 8:
        return "Token looks too short"
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", token):
        return "Token contains invalid characters"
    return ""


def read_dotenv_token(path: Path = ENV_PATH) -> Optional[str]:
    if not path.exists():
        return None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "MARKETDATA_TOKEN":
            return normalize_token(value) or None
    return None


def get_token_info() -> Dict[str, Any]:
    if _ACTIVE_TOKEN:
        format_error = token_format_error(_ACTIVE_TOKEN)
        return {
            "token": _ACTIVE_TOKEN,
            "source": "session",
            "preview": mask_token(_ACTIVE_TOKEN),
            "formatOk": not format_error,
            "formatReason": format_error,
        }

    file_token = read_dotenv_token()
    if file_token:
        format_error = token_format_error(file_token)
        return {
            "token": file_token,
            "source": "file",
            "preview": mask_token(file_token),
            "formatOk": not format_error,
            "formatReason": format_error,
        }

    env_token = os.getenv("MARKETDATA_TOKEN")
    if env_token:
        env_token = normalize_token(env_token)
        format_error = token_format_error(env_token)
        return {
            "token": env_token,
            "source": "env",
            "preview": mask_token(env_token),
            "formatOk": not format_error,
            "formatReason": format_error,
        }

    return {
        "token": None,
        "source": "missing",
        "preview": "",
        "formatOk": False,
        "formatReason": "MarketData token is not configured",
    }


def get_token() -> Optional[str]:
    return get_token_info()["token"]


def test_marketdata_token(token: str) -> Dict[str, Any]:
    cleaned = normalize_token(token)
    format_error = token_format_error(cleaned)
    if format_error:
        return {
            "ok": False,
            "httpStatus": None,
            "reason": format_error,
            "token": cleaned,
        }
    checks = [
        ("/stocks/quotes/SPY/", "stock quote"),
        ("/options/expirations/SPY/", "option expirations"),
    ]
    last_status = None
    for path, label in checks:
        try:
            payload, status = calc.marketdata_get(
                path,
                {},
                cleaned,
                timeout=20,
                retries=1,
            )
        except Exception as exc:
            return {
                "ok": False,
                "httpStatus": last_status,
                "reason": f"{label}: {exc}",
                "token": cleaned,
            }
        last_status = status
        if payload.get("s") == "error":
            return {
                "ok": False,
                "httpStatus": status,
                "reason": f"{label}: {payload.get('errmsg', 'API error')}",
                "token": cleaned,
            }

    return {
        "ok": True,
        "httpStatus": last_status,
        "reason": "",
        "token": cleaned,
    }


def save_token(token: str, path: Path = ENV_PATH, activate: bool = True) -> str:
    global _ACTIVE_TOKEN
    cleaned = normalize_token(token)
    format_error = token_format_error(cleaned)
    if format_error:
        raise ValueError(format_error)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(
        f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
    )
    try:
        fd = os.open(
            temporary_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(f"MARKETDATA_TOKEN={cleaned}\n")
        temporary_path.replace(path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    if activate:
        _ACTIVE_TOKEN = cleaned
    return cleaned


def find_open_port(preferred: int) -> int:
    for port in [preferred, *range(preferred + 1, preferred + 50)]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("No open local port found")


def request_host_name(value: Optional[str]) -> str:
    host = (value or "").strip().lower()
    if not host:
        return ""
    if host.startswith("[") and "]" in host:
        return host[1 : host.index("]")]
    if host.count(":") > 1:
        return host
    return host.split(":", 1)[0]


def is_loopback_host(value: Optional[str]) -> bool:
    if not value or not value.strip():
        return True
    host = request_host_name(value)
    return host in LOOPBACK_HOSTS


def is_loopback_url(value: Optional[str]) -> bool:
    if not value:
        return True
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return False
    return is_loopback_host(parsed.netloc)


def payload_value(payload: Dict[str, Any], key: str, default: Any) -> Any:
    if key not in payload:
        return default
    value = payload[key]
    if value is None:
        return default
    if isinstance(value, str) and value.strip() == "":
        return default
    return value


def payload_int(
    payload: Dict[str, Any],
    key: str,
    default: int,
    minimum: Optional[int] = None,
    maximum: Optional[int] = None,
) -> int:
    raw_value = payload_value(payload, key, default)
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be an integer") from exc
    if minimum is not None and value < minimum:
        raise ValueError(f"{key} must be at least {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{key} must be at most {maximum}")
    return value


def payload_float(
    payload: Dict[str, Any],
    key: str,
    default: Optional[float],
    minimum: Optional[float] = None,
    maximum: Optional[float] = None,
) -> Optional[float]:
    raw_value = payload_value(payload, key, default)
    if raw_value is None:
        return None
    try:
        value = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be a number") from exc
    if not math.isfinite(value):
        raise ValueError(f"{key} must be a finite number")
    if minimum is not None and value < minimum:
        raise ValueError(f"{key} must be at least {minimum:g}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{key} must be at most {maximum:g}")
    return value


def payload_optional_int(
    payload: Dict[str, Any],
    key: str,
    minimum: Optional[int] = None,
    maximum: Optional[int] = None,
) -> Optional[int]:
    raw_value = payload_value(payload, key, None)
    if raw_value is None:
        return None
    return payload_int({key: raw_value}, key, 0, minimum, maximum)


def payload_bool(payload: Dict[str, Any], key: str, default: bool) -> bool:
    raw_value = payload_value(payload, key, default)
    if isinstance(raw_value, bool):
        return raw_value
    if isinstance(raw_value, str):
        value = raw_value.strip().lower()
        if value in {"1", "true", "yes", "on"}:
            return True
        if value in {"0", "false", "no", "off"}:
            return False
        raise ValueError(f"{key} must be a boolean")
    if isinstance(raw_value, (int, float)):
        if raw_value in {0, 1}:
            return bool(raw_value)
        raise ValueError(f"{key} must be a boolean")
    return bool(raw_value)


def payload_choice(
    payload: Dict[str, Any],
    key: str,
    default: str,
    choices: set[str],
) -> str:
    value = str(payload_value(payload, key, default)).strip()
    if value not in choices:
        available = ", ".join(sorted(choices))
        raise ValueError(f"{key} must be one of: {available}")
    return value


def web_file_for_path(request_path: str) -> Optional[Path]:
    safe_path = urllib.parse.unquote(request_path).lstrip("/")
    if not safe_path.startswith("web/"):
        return None
    target = (APP_DIR / safe_path).resolve()
    try:
        target.relative_to(WEB_DIR.resolve())
    except ValueError as exc:
        raise PermissionError("Forbidden path") from exc
    return target


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def parse_json_body(handler: BaseHTTPRequestHandler) -> Dict[str, Any]:
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except ValueError as exc:
        raise ValueError("Invalid Content-Length") from exc
    if length < 0:
        raise ValueError("Invalid Content-Length")
    if length > MAX_JSON_BODY_BYTES:
        raise ValueError("Request body is too large")
    if length == 0:
        return {}
    raw_body = handler.rfile.read(length)
    if len(raw_body) != length:
        raise ValueError("Request body ended before Content-Length")
    try:
        body = raw_body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Request body must be UTF-8") from exc
    try:
        payload = json.loads(body or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("Request body must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    return payload


def default_args() -> argparse.Namespace:
    return argparse.Namespace(
        token=None,
        mode="delayed",
        fallback_mode=None,
        maxage="5min",
        strike_limit=120,
        min_open_interest=None,
        min_volume=None,
        max_bid_ask_spread_pct=200.0,
        target_days=30.0,
        min_days=23.0,
        max_days=37.0,
        min_side_strikes=5,
        max_quote_age_minutes=45.0,
        allow_stale=True,
        allow_extrapolation=False,
        settlement_hour=16,
        settlement_minute=0,
        risk_free_rate=None,
        request_delay_seconds=0.25,
    )


def latest_recorded_values_by_symbol(path: Path = RECORDS_PATH) -> Dict[str, float]:
    """Return the latest usable AssetVIX value for each recorded symbol."""
    _, records = calc.read_csv_rows(str(path))
    latest: Dict[str, float] = {}
    for row in reversed(records):
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol or symbol in latest:
            continue
        value = history_numeric_value(row)
        if value is not None:
            latest[symbol] = value
    return latest


def add_previous_run_comparison(
    rows: List[Dict[str, Any]], previous_values: Dict[str, float]
) -> List[Dict[str, Any]]:
    """Attach ephemeral, per-symbol changes against the prior recorded run."""
    for row in rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        previous = previous_values.get(symbol)
        current = history_numeric_value(row)
        change = current - previous if current is not None and previous is not None else None
        change_percent = (
            (change / previous) * 100
            if change is not None and previous not in (None, 0)
            else None
        )
        row["previous_asset_vix_30d"] = round(previous, 4) if previous is not None else None
        row["change_from_previous"] = round(change, 4) if change is not None else None
        row["change_from_previous_pct"] = (
            round(change_percent, 2) if change_percent is not None else None
        )
    return rows


def compute_rows(payload: Dict[str, Any], token: str) -> List[Dict[str, Any]]:
    args = default_args()
    args.token = token
    args.mode = payload_choice(
        payload, "mode", args.mode, {"cached", "delayed", "live"}
    )
    fallback_mode = payload_value(payload, "fallbackMode", None)
    if fallback_mode is not None:
        fallback_mode = payload_choice(
            {"fallbackMode": fallback_mode},
            "fallbackMode",
            "",
            {"delayed", "live"},
        )
    args.fallback_mode = fallback_mode
    args.maxage = str(payload_value(payload, "maxage", args.maxage))
    args.strike_limit = payload_int(payload, "strikeLimit", args.strike_limit, 1, 1000)
    args.min_open_interest = payload_optional_int(payload, "minOpenInterest", 0)
    args.min_volume = payload_optional_int(payload, "minVolume", 0)
    args.min_side_strikes = payload_int(
        payload, "minSideStrikes", args.min_side_strikes, 1, 100
    )
    args.max_bid_ask_spread_pct = payload_float(
        payload, "maxBidAskSpreadPct", args.max_bid_ask_spread_pct, 0
    )
    if args.max_bid_ask_spread_pct <= 0:
        args.max_bid_ask_spread_pct = None
    args.max_quote_age_minutes = payload_float(
        payload, "maxQuoteAgeMinutes", args.max_quote_age_minutes, 0
    )
    args.request_delay_seconds = payload_float(
        payload, "requestDelaySeconds", args.request_delay_seconds, 0, 60
    )
    args.allow_stale = payload_bool(payload, "allowStale", args.allow_stale)
    args.allow_extrapolation = payload_bool(
        payload, "allowExtrapolation", args.allow_extrapolation
    )
    args.target_days = payload_float(payload, "targetDays", args.target_days, 0.1)
    args.risk_free_rate = payload_float(
        payload, "riskFreeRate", None, -1, 1
    )

    raw_symbols = "SPY" if "symbols" not in payload else str(payload["symbols"])
    try:
        symbols = calc.parse_symbols(raw_symbols)
    except calc.AssetVixError as exc:
        raise ValueError(str(exc)) from exc
    if not symbols:
        raise ValueError("Enter at least one symbol")
    if len(symbols) > MAX_QUERY_SYMBOLS:
        raise ValueError(
            f"A query can include at most {MAX_QUERY_SYMBOLS} unique symbols"
        )

    previous_values = latest_recorded_values_by_symbol(RECORDS_PATH)
    rows = calc.compute_symbols(symbols, args)
    recorded_rows = calc.record_rows(str(RECORDS_PATH), rows, source="web")
    return add_previous_run_comparison(recorded_rows, previous_values)


def csv_rows_bytes(
    rows: List[Dict[str, Any]],
    fieldnames: Optional[List[str]] = None,
) -> bytes:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=fieldnames or RECORD_HEADERS,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(calc.csv_safe_row(row) for row in rows)
    return output.getvalue().encode("utf-8")


def records_csv_bytes(path: Path = RECORDS_PATH) -> bytes:
    fieldnames, rows = calc.read_csv_rows(str(path))
    return csv_rows_bytes(rows, fieldnames or RECORD_HEADERS)


def records_json_bytes(path: Path = RECORDS_PATH) -> bytes:
    _, rows = calc.read_csv_rows(str(path))
    payload = {
        "version": calc.VERSION,
        "exported_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(
            timespec="seconds"
        ),
        "count": len(rows),
        "rows": rows,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def parse_history_query(query_string: str) -> tuple[int, Optional[str], str, int]:
    query = urllib.parse.parse_qs(query_string)
    try:
        limit = int((query.get("limit") or ["25"])[0])
    except ValueError:
        limit = 25
    symbol = (query.get("symbol") or [None])[0]
    status = (query.get("status") or ["__all__"])[0]
    try:
        window_days = int((query.get("windowDays") or ["0"])[0])
    except ValueError:
        window_days = -1
    return limit, symbol, status, window_days


def history_status_bucket(status: Any) -> str:
    normalized = str(status or "").strip().lower()
    if normalized == "ok":
        return "ok"
    if normalized == "error":
        return "error"
    return "warn"


def history_window_days(value: Any) -> int:
    """Return an allowed rolling-history window, where zero means all records."""
    try:
        days = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("windowDays must be one of: 0, 7, 30, 90, 365") from exc
    if days not in {0, 7, 30, 90, 365}:
        raise ValueError("windowDays must be one of: 0, 7, 30, 90, 365")
    return days


def history_recorded_at(row: Dict[str, Any]) -> Optional[dt.datetime]:
    raw_value = str(row.get("recorded_at_utc") or row.get("ts_utc") or "").strip()
    if not raw_value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def history_payload(
    path: Path = RECORDS_PATH,
    limit: int = 25,
    symbol: Optional[str] = None,
    status: str = "__all__",
    window_days: int = 0,
    now: Optional[dt.datetime] = None,
) -> Dict[str, Any]:
    limit = min(max(int(limit), 1), 500)
    _, rows = calc.read_csv_rows(str(path))
    symbols = sorted(
        {
            str(row.get("symbol") or "").upper()
            for row in rows
            if str(row.get("symbol") or "").strip()
        }
    )

    selected_symbol = ""
    if symbol and str(symbol).strip().lower() not in {"__all__", "all"}:
        try:
            selected_symbol = calc.validate_symbol(symbol)
        except calc.AssetVixError as exc:
            raise ValueError(str(exc)) from exc

    selected_status = str(status or "__all__").strip().lower()
    if selected_status in {"", "__all__", "all"}:
        selected_status = "__all__"
    elif selected_status not in {"ok", "warn", "error"}:
        raise ValueError("status must be one of: all, ok, warn, error")

    selected_window_days = history_window_days(window_days)

    filtered = rows
    if selected_symbol:
        filtered = [
            row
            for row in filtered
            if str(row.get("symbol") or "").upper() == selected_symbol
        ]
    if selected_status != "__all__":
        filtered = [
            row
            for row in filtered
            if history_status_bucket(row.get("status")) == selected_status
        ]
    if selected_window_days:
        reference_time = now or dt.datetime.now(dt.timezone.utc)
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=dt.timezone.utc)
        cutoff = reference_time.astimezone(dt.timezone.utc) - dt.timedelta(
            days=selected_window_days
        )
        filtered = [
            row
            for row in filtered
            if (recorded_at := history_recorded_at(row)) is not None
            and recorded_at >= cutoff
        ]

    recent_rows = filtered[-limit:]
    return {
        "ok": True,
        "rows": recent_rows,
        "count": len(recent_rows),
        "matchedCount": len(filtered),
        "totalCount": len(rows),
        "symbols": symbols,
        "windowDays": selected_window_days,
        "recordsPath": str(path),
    }


def history_csv_bytes(
    path: Path = RECORDS_PATH,
    limit: int = 25,
    symbol: Optional[str] = None,
    status: str = "__all__",
    window_days: int = 0,
) -> bytes:
    payload = history_payload(path, limit, symbol, status, window_days)
    return csv_rows_bytes(payload["rows"], RECORD_HEADERS)


def history_json_bytes(
    path: Path = RECORDS_PATH,
    limit: int = 25,
    symbol: Optional[str] = None,
    status: str = "__all__",
    window_days: int = 0,
) -> bytes:
    payload = history_payload(path, limit, symbol, status, window_days)
    payload.update(
        {
            "version": calc.VERSION,
            "exported_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(
                timespec="seconds"
            ),
            "filters": {
                "limit": min(max(int(limit), 1), 500),
                "symbol": symbol or "__all__",
                "status": status or "__all__",
                "windowDays": history_window_days(window_days),
            },
        }
    )
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def history_numeric_value(row: Dict[str, Any]) -> Optional[float]:
    if history_status_bucket(row.get("status")) == "error":
        return None
    try:
        value = float(str(row.get("asset_vix_30d") or "").strip())
    except ValueError:
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return value


def history_summary_payload(
    path: Path = RECORDS_PATH,
    limit: int = 500,
    symbol: Optional[str] = None,
    status: str = "__all__",
    window_days: int = 0,
) -> Dict[str, Any]:
    payload = history_payload(path, limit, symbol, status, window_days)
    points: List[Dict[str, Any]] = []
    for row in payload["rows"]:
        value = history_numeric_value(row)
        if value is None:
            continue
        points.append(
            {
                "value": value,
                "symbol": str(row.get("symbol") or "").upper(),
                "recorded_at_utc": row.get("recorded_at_utc") or row.get("ts_utc") or "",
                "status": row.get("status") or "",
            }
        )

    values = [point["value"] for point in points]
    latest = points[-1] if points else None
    previous = points[-2] if len(points) >= 2 else None
    change = (
        latest["value"] - previous["value"]
        if latest is not None and previous is not None
        else None
    )
    change_percent = (
        (change / previous["value"]) * 100
        if change is not None and previous is not None and previous["value"] != 0
        else None
    )
    if change is None:
        trend = "flat"
    elif abs(change) < 0.000001:
        trend = "flat"
    elif change > 0:
        trend = "up"
    else:
        trend = "down"

    sorted_values = sorted(values)
    middle = len(sorted_values) // 2
    median = (
        sorted_values[middle]
        if len(sorted_values) % 2
        else (sorted_values[middle - 1] + sorted_values[middle]) / 2
    ) if sorted_values else None
    percentile = (
        sum(value <= latest["value"] for value in values) / len(values) * 100
        if latest is not None and values
        else None
    )
    if percentile is None:
        regime = "unknown"
    elif percentile >= 80:
        regime = "high"
    elif percentile <= 20:
        regime = "low"
    else:
        regime = "normal"

    return {
        "ok": True,
        "count": payload["count"],
        "matchedCount": payload["matchedCount"],
        "totalCount": payload["totalCount"],
        "numericCount": len(values),
        "latest": latest,
        "previous": previous,
        "change": round(change, 4) if change is not None else None,
        "changePercent": round(change_percent, 2) if change_percent is not None else None,
        "trend": trend,
        "average": round(math.fsum(values) / len(values), 4) if values else None,
        "median": round(median, 4) if median is not None else None,
        "low": round(min(values), 4) if values else None,
        "high": round(max(values), 4) if values else None,
        "percentile": round(percentile, 1) if percentile is not None else None,
        "regime": regime,
        "filters": {
            "limit": min(max(int(limit), 1), 500),
            "symbol": symbol or "__all__",
            "status": status or "__all__",
            "windowDays": payload["windowDays"],
        },
    }


def universes_payload(path: Path = UNIVERSE_PATH) -> Dict[str, Any]:
    try:
        universes = calc.load_symbol_universes(str(path))
    except calc.AssetVixError as exc:
        raise ValueError(str(exc)) from exc

    preferred = ["core", "etfs", "mega_cap", "semis", "liquid50", "liquid100"]
    names = [name for name in preferred if name in universes]
    names.extend(name for name in sorted(universes) if name not in set(names))
    return {
        "ok": True,
        "universes": [
            {
                "name": name,
                "count": len(universes[name]),
                "symbols": universes[name],
            }
            for name in names
        ],
    }


class AssetVixHandler(BaseHTTPRequestHandler):
    server_version = f"AssetVIXLocal/{calc.VERSION}"

    def version_string(self) -> str:
        return self.server_version

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[AssetVIX] " + fmt % args + "\n")

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
            "base-uri 'none'; form-action 'self'",
        )
        self.send_header(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
        super().end_headers()

    def send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def send_file(self, path: Path, head_only: bool = False) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if not head_only:
            self.wfile.write(data)

    def send_web_path(self, request_path: str, head_only: bool = False) -> bool:
        target = web_file_for_path(request_path)
        if target is None:
            return False
        self.send_file(target, head_only=head_only)
        return True

    def send_records_csv(self, head_only: bool = False) -> None:
        data = records_csv_bytes(RECORDS_PATH)

        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header(
            "Content-Disposition",
            'attachment; filename="assetvix-records.csv"',
        )
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if not head_only:
            self.wfile.write(data)

    def send_records_json(self, head_only: bool = False) -> None:
        data = records_json_bytes(RECORDS_PATH)

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header(
            "Content-Disposition",
            'attachment; filename="assetvix-records.json"',
        )
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if not head_only:
            self.wfile.write(data)

    def send_history_csv(self, query_string: str, head_only: bool = False) -> None:
        limit, symbol, status, window_days = parse_history_query(query_string)
        try:
            data = history_csv_bytes(
                RECORDS_PATH, limit, symbol, status, window_days
            )
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header(
            "Content-Disposition",
            'attachment; filename="assetvix-filtered-history.csv"',
        )
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if not head_only:
            self.wfile.write(data)

    def send_history_json(self, query_string: str, head_only: bool = False) -> None:
        limit, symbol, status, window_days = parse_history_query(query_string)
        try:
            data = history_json_bytes(
                RECORDS_PATH, limit, symbol, status, window_days
            )
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header(
            "Content-Disposition",
            'attachment; filename="assetvix-filtered-history.json"',
        )
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if not head_only:
            self.wfile.write(data)

    def reject_unsafe_request(self, check_origin: bool = False) -> bool:
        if not is_loopback_host(self.headers.get("Host")):
            self.send_error(HTTPStatus.FORBIDDEN, "Forbidden host")
            return True
        if check_origin:
            origin = self.headers.get("Origin")
            referer = self.headers.get("Referer")
            if not is_loopback_url(origin) or not is_loopback_url(referer):
                self.send_json(
                    {"ok": False, "error": "Forbidden request origin"},
                    status=HTTPStatus.FORBIDDEN,
                )
                return True
        return False

    def do_HEAD(self) -> None:
        if self.reject_unsafe_request():
            return
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/records.csv":
            self.send_records_csv(head_only=True)
            return
        if parsed.path == "/api/records.json":
            self.send_records_json(head_only=True)
            return
        if parsed.path == "/api/history.csv":
            self.send_history_csv(parsed.query, head_only=True)
            return
        if parsed.path == "/api/history.json":
            self.send_history_json(parsed.query, head_only=True)
            return
        if parsed.path in {"/", "/index.html"}:
            self.send_file(WEB_DIR / "index.html", head_only=True)
            return
        try:
            if self.send_web_path(parsed.path, head_only=True):
                return
        except PermissionError:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_GET(self) -> None:
        if self.reject_unsafe_request():
            return
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/status":
            token_info = get_token_info()
            self.send_json(
                {
                    "ok": True,
                    "version": calc.VERSION,
                    "tokenConfigured": bool(token_info["token"]),
                    "tokenSource": token_info["source"],
                    "tokenPreview": token_info["preview"],
                    "tokenFormatOk": token_info["formatOk"],
                    "tokenFormatReason": token_info["formatReason"],
                    "recordsPath": str(RECORDS_PATH),
                }
                )
            return

        if parsed.path == "/api/history":
            limit, symbol, status, window_days = parse_history_query(parsed.query)
            try:
                self.send_json(
                    history_payload(RECORDS_PATH, limit, symbol, status, window_days)
                )
            except ValueError as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return

        if parsed.path == "/api/history/summary":
            limit, symbol, status, window_days = parse_history_query(parsed.query)
            try:
                self.send_json(
                    history_summary_payload(
                        RECORDS_PATH, limit, symbol, status, window_days
                    )
                )
            except ValueError as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return

        if parsed.path == "/api/records.csv":
            self.send_records_csv()
            return

        if parsed.path == "/api/records.json":
            self.send_records_json()
            return

        if parsed.path == "/api/history.csv":
            self.send_history_csv(parsed.query)
            return

        if parsed.path == "/api/history.json":
            self.send_history_json(parsed.query)
            return

        if parsed.path == "/api/universes":
            try:
                self.send_json(universes_payload(UNIVERSE_PATH))
            except ValueError as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return

        if parsed.path in {"/", "/index.html"}:
            self.send_file(WEB_DIR / "index.html")
            return

        try:
            if self.send_web_path(parsed.path):
                return
        except PermissionError:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.reject_unsafe_request(check_origin=True):
            return
        try:
            payload = parse_json_body(self)
            if self.path == "/api/token/test":
                token = str(payload.get("token") or "").strip()
                if len(token) < 8:
                    self.send_json(
                        {
                            "ok": False,
                            "valid": False,
                            "error": "Token looks too short",
                        },
                        status=400,
                    )
                    return
                validation = test_marketdata_token(token)
                if not validation["ok"]:
                    self.send_json(
                        {
                            "ok": False,
                            "valid": False,
                            "error": validation["reason"] or "Token test failed",
                        },
                        status=400,
                    )
                    return
                self.send_json(
                    {
                        "ok": True,
                        "valid": True,
                        "httpStatus": validation["httpStatus"],
                        "tokenPreview": mask_token(validation["token"]),
                    }
                )
                return

            if self.path == "/api/token":
                token = str(payload.get("token") or "")
                validation = test_marketdata_token(token)
                if not validation["ok"]:
                    self.send_json(
                        {
                            "ok": False,
                            "valid": False,
                            "error": validation["reason"] or "Token test failed",
                        },
                        status=400,
                    )
                    return
                cleaned = save_token(token)
                self.send_json(
                    {
                        "ok": True,
                        "valid": True,
                        "tokenConfigured": True,
                        "tokenSource": "session",
                        "tokenPreview": mask_token(cleaned),
                        "httpStatus": validation["httpStatus"],
                    }
                )
                return

            if self.path == "/api/query":
                token_info = get_token_info()
                token = token_info["token"]
                if not token:
                    self.send_json(
                        {
                            "ok": False,
                            "error": "MarketData token is not configured",
                        },
                        status=400,
                    )
                    return
                if not token_info["formatOk"]:
                    self.send_json(
                        {
                            "ok": False,
                            "error": token_info["formatReason"],
                        },
                        status=400,
                    )
                    return
                rows = compute_rows(payload, token)
                self.send_json({"ok": True, "rows": rows})
                return

            if self.path == "/api/history/clear":
                cleared = calc.clear_csv_rows(str(RECORDS_PATH))
                self.send_json({"ok": True, "cleared": cleared, "rows": []})
                return

            self.send_error(HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:
            self.log_error("Unhandled request error: %s", exc)
            self.send_json(
                {"ok": False, "error": "Internal server error"},
                status=500,
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local AssetVIX web app.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    port = find_open_port(args.port)
    server = ReusableThreadingHTTPServer(("127.0.0.1", port), AssetVixHandler)
    url = f"http://127.0.0.1:{port}/"

    print(f"AssetVIX is running at {url}")
    print("Keep this window open. Press Ctrl-C to stop.")

    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping AssetVIX.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
