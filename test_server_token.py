import importlib.util
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


if __name__ == "__main__":
    unittest.main()
