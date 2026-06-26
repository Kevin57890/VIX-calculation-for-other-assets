import csv
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest


SERVER_PATH = Path(__file__).with_name("server.py")
CALC_PATH = Path(__file__).with_name("asset_vix.py")

CALC_SPEC = importlib.util.spec_from_file_location("asset_vix", CALC_PATH)
calc_module = importlib.util.module_from_spec(CALC_SPEC)
assert CALC_SPEC.loader is not None
sys.modules["asset_vix"] = calc_module
CALC_SPEC.loader.exec_module(calc_module)

SPEC = importlib.util.spec_from_file_location("asset_vix_server_module", SERVER_PATH)
server = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.path.insert(0, str(SERVER_PATH.parent))
sys.modules[SPEC.name] = server
SPEC.loader.exec_module(server)


class ServerTokenTests(unittest.TestCase):
    def setUp(self):
        self.old_active = server._ACTIVE_TOKEN
        self.old_env = os.environ.get("MARKETDATA_TOKEN")
        server._ACTIVE_TOKEN = None

    def tearDown(self):
        server._ACTIVE_TOKEN = self.old_active
        if self.old_env is None:
            os.environ.pop("MARKETDATA_TOKEN", None)
        else:
            os.environ["MARKETDATA_TOKEN"] = self.old_env

    def test_saved_session_token_takes_precedence(self):
        os.environ["MARKETDATA_TOKEN"] = "env-token-12345678901234567890"
        with tempfile.NamedTemporaryFile(delete=False) as handle:
            path = Path(handle.name)
        try:
            server.save_token(
                "file-token-12345678901234567890",
                path=path,
                activate=False,
            )
            self.assertEqual(
                server.read_dotenv_token(path),
                "file-token-12345678901234567890",
            )

            server.save_token(
                "session-token-12345678901234567890",
                path=path,
                activate=True,
            )
            info = server.get_token_info()
            self.assertEqual(info["source"], "session")
            self.assertEqual(info["token"], "session-token-12345678901234567890")
            self.assertTrue(info["preview"].endswith("7890"))
        finally:
            path.unlink(missing_ok=True)

    def test_save_token_creates_parent_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / ".env"
            cleaned = server.save_token(
                "nested-token-1234567890",
                path=path,
                activate=False,
            )
            self.assertEqual(cleaned, "nested-token-1234567890")
            self.assertEqual(server.read_dotenv_token(path), "nested-token-1234567890")
            self.assertFalse(path.with_suffix(f"{path.suffix}.tmp").exists())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_save_token_rejects_invalid_token_format(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            with self.assertRaisesRegex(ValueError, "invalid characters"):
                server.save_token("bad,token-123456", path=path, activate=False)
            self.assertFalse(path.exists())

    def test_normalize_common_token_paste_formats(self):
        cases = {
            "Bearer ABC123xyz": "ABC123xyz",
            "Authorization: Bearer ABC123xyz": "ABC123xyz",
            "MARKETDATA_TOKEN=ABC123xyz": "ABC123xyz",
            "api Key,ABC123xyz": "ABC123xyz",
            "ABC 123 xyz": "ABC123xyz",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(server.normalize_token(raw), expected)

    def test_token_format_error_catches_bad_characters(self):
        self.assertEqual(server.token_format_error("ABC123xyz"), "")
        self.assertEqual(
            server.token_format_error("ABC,123456"),
            "Token contains invalid characters",
        )

    def test_marketdata_token_validation_success(self):
        original = server.calc.marketdata_get
        try:
            server.calc.marketdata_get = lambda *args, **kwargs: ({"s": "ok"}, 200)
            result = server.test_marketdata_token("valid-token-123456")
            self.assertTrue(result["ok"])
            self.assertEqual(result["httpStatus"], 200)
        finally:
            server.calc.marketdata_get = original

    def test_marketdata_token_validation_failure(self):
        original = server.calc.marketdata_get
        try:
            def fail(*args, **kwargs):
                raise server.calc.AssetVixError("MarketData HTTP 401: Invalid token.")

            server.calc.marketdata_get = fail
            result = server.test_marketdata_token("bad-token-123456")
            self.assertFalse(result["ok"])
            self.assertIn("Invalid token", result["reason"])
        finally:
            server.calc.marketdata_get = original

    def test_compute_rows_records_web_results(self):
        original_compute = server.calc.compute_symbols
        original_records_path = server.RECORDS_PATH
        with tempfile.TemporaryDirectory() as directory:
            try:
                server.RECORDS_PATH = Path(directory) / "records" / "calculations.csv"

                def fake_compute(symbols, args):
                    self.assertEqual(symbols, ["SPY"])
                    self.assertEqual(args.token, "valid-token-123456")
                    return [
                        {
                            "ts_utc": "2026-01-01T00:00:00+00:00",
                            "symbol": "SPY",
                            "status": "ok",
                            "asset_vix_30d": 18.5,
                        }
                    ]

                server.calc.compute_symbols = fake_compute
                rows = server.compute_rows({"symbols": "SPY"}, "valid-token-123456")
                self.assertEqual(rows[0]["source"], "web")
                self.assertIn("run_id", rows[0])
                self.assertTrue(server.RECORDS_PATH.exists())

                recent = server.calc.read_recent_csv_rows(str(server.RECORDS_PATH), limit=1)
                self.assertEqual(recent[0]["symbol"], "SPY")
                self.assertEqual(recent[0]["source"], "web")
            finally:
                server.calc.compute_symbols = original_compute
                server.RECORDS_PATH = original_records_path

    def test_compute_rows_preserves_zero_overrides(self):
        original_compute = server.calc.compute_symbols
        original_records_path = server.RECORDS_PATH
        with tempfile.TemporaryDirectory() as directory:
            try:
                server.RECORDS_PATH = Path(directory) / "records" / "calculations.csv"

                def fake_compute(symbols, args):
                    self.assertEqual(symbols, ["SPY"])
                    self.assertIsNone(args.max_bid_ask_spread_pct)
                    self.assertEqual(args.max_quote_age_minutes, 0)
                    self.assertEqual(args.request_delay_seconds, 0)
                    self.assertEqual(args.risk_free_rate, 0)
                    self.assertFalse(args.allow_stale)
                    self.assertTrue(args.allow_extrapolation)
                    return [
                        {
                            "ts_utc": "2026-01-01T00:00:00+00:00",
                            "symbol": "SPY",
                            "status": "ok",
                            "asset_vix_30d": 18.5,
                        }
                    ]

                server.calc.compute_symbols = fake_compute
                rows = server.compute_rows(
                    {
                        "symbols": "SPY",
                        "maxBidAskSpreadPct": 0,
                        "maxQuoteAgeMinutes": 0,
                        "requestDelaySeconds": 0,
                        "riskFreeRate": 0,
                        "allowStale": "false",
                        "allowExtrapolation": "true",
                    },
                    "valid-token-123456",
                )
                self.assertEqual(rows[0]["symbol"], "SPY")
            finally:
                server.calc.compute_symbols = original_compute
                server.RECORDS_PATH = original_records_path

    def test_records_csv_bytes_escapes_existing_formula_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calculations.csv"
            path.write_text(
                "symbol,status,reason\n"
                "SPY,ok,=HYPERLINK(\"https://example.com\")\n"
                "QQQ,ok,\t@cmd\n",
                encoding="utf-8",
            )

            data = server.records_csv_bytes(path).decode("utf-8")
            rows = list(csv.DictReader(io.StringIO(data)))
            self.assertEqual(
                rows[0]["reason"],
                "'=HYPERLINK(\"https://example.com\")",
            )
            self.assertEqual(rows[1]["reason"], "'\t@cmd")

    def test_records_csv_bytes_returns_headers_without_records_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.csv"
            data = server.records_csv_bytes(path).decode("utf-8")
            self.assertEqual(data.splitlines()[0], ",".join(server.RECORD_HEADERS))

    def test_universes_payload_returns_ordered_universes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "universes.csv"
            path.write_text(
                "symbol,groups,tier,active\n"
                "SPY,core|etfs,tier1,true\n"
                "AAPL,core|mega_cap,tier1,true\n",
                encoding="utf-8",
            )

            payload = server.universes_payload(path)
            names = [item["name"] for item in payload["universes"]]
            self.assertEqual(names[:3], ["core", "etfs", "mega_cap"])
            self.assertEqual(payload["universes"][0]["symbols"], ["SPY", "AAPL"])

    def test_universes_payload_reports_invalid_symbols(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "universes.csv"
            path.write_text(
                "symbol,groups,tier,active\n"
                "SPY,core,tier1,true\n"
                "BAD/../SYM,core,tier1,true\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "Invalid symbol"):
                server.universes_payload(path)

    def test_compute_rows_rejects_invalid_numeric_payload(self):
        with self.assertRaisesRegex(ValueError, "strikeLimit must be at least 1"):
            server.compute_rows({"symbols": "SPY", "strikeLimit": 0}, "valid-token-123456")

    def test_compute_rows_rejects_invalid_symbol_as_bad_request_error(self):
        with self.assertRaisesRegex(ValueError, "Invalid symbol"):
            server.compute_rows({"symbols": "SPY/../AAPL"}, "valid-token-123456")

    def test_compute_rows_rejects_empty_symbol_payload(self):
        with self.assertRaisesRegex(ValueError, "Enter at least one symbol"):
            server.compute_rows({"symbols": "  , ;  "}, "valid-token-123456")

    def test_payload_bool_rejects_ambiguous_values(self):
        self.assertFalse(server.payload_bool({"flag": 0}, "flag", True))
        self.assertTrue(server.payload_bool({"flag": 1}, "flag", False))
        with self.assertRaisesRegex(ValueError, "flag must be a boolean"):
            server.payload_bool({"flag": "maybe"}, "flag", False)
        with self.assertRaisesRegex(ValueError, "flag must be a boolean"):
            server.payload_bool({"flag": 2}, "flag", False)

    def test_parse_json_body_rejects_large_payloads(self):
        class FakeHandler:
            headers = {"Content-Length": str(server.MAX_JSON_BODY_BYTES + 1)}
            rfile = io.BytesIO(b"")

        with self.assertRaisesRegex(ValueError, "Request body is too large"):
            server.parse_json_body(FakeHandler())

    def test_web_file_for_path_rejects_path_escape(self):
        self.assertEqual(
            server.web_file_for_path("/web/styles.css"),
            (server.WEB_DIR / "styles.css").resolve(),
        )
        with self.assertRaises(PermissionError):
            server.web_file_for_path("/web/../server.py")
        with self.assertRaises(PermissionError):
            server.web_file_for_path("/web/%2e%2e/server.py")

    def test_loopback_request_boundary_checks(self):
        self.assertTrue(server.is_loopback_host(""))
        self.assertTrue(server.is_loopback_host("127.0.0.1:8765"))
        self.assertTrue(server.is_loopback_host("localhost"))
        self.assertTrue(server.is_loopback_host("[::1]:8765"))
        self.assertTrue(server.is_loopback_host("::1"))
        self.assertFalse(server.is_loopback_host("example.com"))
        self.assertFalse(server.is_loopback_host(":8765"))

        self.assertTrue(server.is_loopback_url(None))
        self.assertTrue(server.is_loopback_url("http://127.0.0.1:8765/"))
        self.assertTrue(server.is_loopback_url("http://localhost:8765/web/index.html"))
        self.assertFalse(server.is_loopback_url("https://example.com/"))
        self.assertFalse(server.is_loopback_url("null"))


if __name__ == "__main__":
    unittest.main()
