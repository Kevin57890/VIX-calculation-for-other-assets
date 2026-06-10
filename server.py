#!/usr/bin/env python3
"""Local click-to-query web app for AssetVIX."""

from __future__ import annotations

import argparse
import json
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
RESULTS_PATH = APP_DIR / "results.csv"
UNIVERSE_PATH = APP_DIR / "universes.csv"
_ACTIVE_TOKEN: Optional[str] = None


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
    if len(cleaned) < 8:
        raise ValueError("Token looks too short")
    path.write_text(f"MARKETDATA_TOKEN={cleaned}\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
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


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def parse_json_body(handler: BaseHTTPRequestHandler) -> Dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    body = handler.rfile.read(length).decode("utf-8")
    return json.loads(body or "{}")


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


def compute_rows(payload: Dict[str, Any], token: str) -> List[Dict[str, Any]]:
    args = default_args()
    args.token = token
    args.mode = str(payload.get("mode") or args.mode)
    args.fallback_mode = payload.get("fallbackMode") or None
    args.maxage = str(payload.get("maxage") or args.maxage)
    args.strike_limit = int(payload.get("strikeLimit") or args.strike_limit)
    args.min_side_strikes = int(payload.get("minSideStrikes") or args.min_side_strikes)
    args.max_bid_ask_spread_pct = float(
        payload.get("maxBidAskSpreadPct") or args.max_bid_ask_spread_pct
    )
    if args.max_bid_ask_spread_pct <= 0:
        args.max_bid_ask_spread_pct = None
    args.max_quote_age_minutes = float(
        payload.get("maxQuoteAgeMinutes") or args.max_quote_age_minutes
    )
    args.request_delay_seconds = float(
        payload.get("requestDelaySeconds") or args.request_delay_seconds
    )
    args.allow_stale = bool(payload.get("allowStale", args.allow_stale))
    args.allow_extrapolation = bool(
        payload.get("allowExtrapolation", args.allow_extrapolation)
    )
    args.target_days = float(payload.get("targetDays") or args.target_days)
    args.risk_free_rate = (
        float(payload["riskFreeRate"]) if payload.get("riskFreeRate") else None
    )

    raw_symbols = str(payload.get("symbols") or "SPY")
    symbols = calc.parse_symbols(raw_symbols)
    if not symbols:
        raise ValueError("Enter at least one symbol")

    rows = calc.compute_symbols(symbols, args)
    calc.write_csv_rows(str(RESULTS_PATH), rows)
    return rows


class AssetVixHandler(BaseHTTPRequestHandler):
    server_version = "AssetVIXLocal/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[asset-vix] " + fmt % args + "\n")

    def send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def send_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_HEAD(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        target = WEB_DIR / "index.html" if parsed.path in {"/", "/index.html"} else None
        if target is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/status":
            token_info = get_token_info()
            self.send_json(
                {
                    "ok": True,
                    "tokenConfigured": bool(token_info["token"]),
                    "tokenSource": token_info["source"],
                    "tokenPreview": token_info["preview"],
                    "tokenFormatOk": token_info["formatOk"],
                    "tokenFormatReason": token_info["formatReason"],
                    "resultsPath": str(RESULTS_PATH),
                }
                )
            return

        if parsed.path == "/api/universes":
            universes = calc.load_symbol_universes(str(UNIVERSE_PATH))
            preferred = ["core", "etfs", "mega_cap", "semis", "liquid50", "liquid100"]
            names = [name for name in preferred if name in universes]
            names.extend(name for name in sorted(universes) if name not in set(names))
            self.send_json(
                {
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
            )
            return

        if parsed.path in {"/", "/index.html"}:
            self.send_file(WEB_DIR / "index.html")
            return

        safe_path = parsed.path.lstrip("/")
        if not safe_path.startswith("web/"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        target = (APP_DIR / safe_path).resolve()
        if not str(target).startswith(str(WEB_DIR.resolve())):
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        self.send_file(target)

    def do_POST(self) -> None:
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

            self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=500)


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
