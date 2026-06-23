import datetime as dt
import importlib.util
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest


MODULE_PATH = Path(__file__).with_name("asset_vix.py")
SPEC = importlib.util.spec_from_file_location("asset_vix_module", MODULE_PATH)
asset_vix = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = asset_vix
SPEC.loader.exec_module(asset_vix)


def norm_cdf(value):
    return 0.5 * (1 + math.erf(value / math.sqrt(2)))


def bs_price(spot, strike, years, rate, vol, side):
    d1 = (math.log(spot / strike) + (rate + 0.5 * vol * vol) * years) / (
        vol * math.sqrt(years)
    )
    d2 = d1 - vol * math.sqrt(years)
    if side == "call":
        return spot * norm_cdf(d1) - strike * math.exp(-rate * years) * norm_cdf(d2)
    return strike * math.exp(-rate * years) * norm_cdf(-d2) - spot * norm_cdf(-d1)


class AssetVixTests(unittest.TestCase):
    def test_unix_timestamp_normalization_accepts_common_epoch_units(self):
        self.assertEqual(asset_vix._to_unix_seconds(1_700_000_000), 1_700_000_000)
        self.assertEqual(asset_vix._to_unix_seconds(1_700_000_000_000), 1_700_000_000)
        self.assertEqual(
            asset_vix._to_unix_seconds(1_700_000_000_000_000),
            1_700_000_000,
        )
        self.assertEqual(
            asset_vix._to_unix_seconds(1_700_000_000_000_000_000),
            1_700_000_000,
        )

    def test_universe_loader_and_resolver(self):
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as handle:
            handle.write("symbol,groups,tier,active\n")
            handle.write("SPY,core|etfs,tier1,true\n")
            handle.write("AAPL,core|mega_cap,tier1,true\n")
            handle.write("XYZ,thin,tier3,false\n")
            path = handle.name
        try:
            universes = asset_vix.load_symbol_universes(path)
            self.assertEqual(universes["core"], ["SPY", "AAPL"])
            symbols = asset_vix.resolve_symbols("MSFT,AAPL", "core", path, None)
            self.assertEqual(symbols, ["SPY", "AAPL", "MSFT"])
        finally:
            os.unlink(path)

    def test_delta_k_uses_edge_and_midpoint_intervals(self):
        strikes = [90.0, 95.0, 100.0, 110.0]
        self.assertEqual(asset_vix.delta_k(strikes, 0), 5.0)
        self.assertEqual(asset_vix.delta_k(strikes, 1), 5.0)
        self.assertEqual(asset_vix.delta_k(strikes, 2), 7.5)
        self.assertEqual(asset_vix.delta_k(strikes, 3), 10.0)

    def test_vix_term_variance_matches_reference_formula(self):
        strikes = [90.0, 95.0, 100.0, 105.0, 110.0]
        prices = {
            90.0: 0.7,
            95.0: 1.2,
            100.0: 2.0,
            105.0: 1.4,
            110.0: 0.9,
        }
        forward = 101.25
        k0 = 100.0
        rate = 0.04
        years = 30 / 365
        expected_sum = sum(
            asset_vix.delta_k(strikes, index)
            / (strike * strike)
            * math.exp(rate * years)
            * prices[strike]
            for index, strike in enumerate(strikes)
        )
        expected = (2 / years) * expected_sum - ((forward / k0 - 1) ** 2) / years
        actual = asset_vix.vix_term_variance(strikes, prices, forward, k0, rate, years)
        self.assertAlmostEqual(actual, expected, places=14)

    def test_missing_quote_ages_stay_missing(self):
        def term(age):
            return asset_vix.TermVariance(
                expiration="2026-02-01",
                days=30,
                years=30 / 365,
                rate=0.04,
                forward=100,
                k0=100,
                variance=0.04,
                strike_count=20,
                put_count=10,
                call_count=10,
                max_quote_age_seconds=age,
            )

        self.assertIsNone(asset_vix.max_term_quote_age_seconds([term(None)]))
        self.assertEqual(
            asset_vix.max_term_quote_age_seconds([term(None), term(90.0)]),
            90.0,
        )

    def test_choose_expirations_uses_vix_window(self):
        now = dt.datetime(2026, 1, 1, 16, 0, tzinfo=asset_vix.ET_ZONE)
        expirations = [
            (now + dt.timedelta(days=20)).date().isoformat(),
            (now + dt.timedelta(days=25)).date().isoformat(),
            (now + dt.timedelta(days=35)).date().isoformat(),
            (now + dt.timedelta(days=40)).date().isoformat(),
        ]
        selected = asset_vix.choose_expirations(
            expirations=expirations,
            now_et=now,
            target_days=30,
            min_days=23,
            max_days=37,
            settlement_hour=16,
            settlement_minute=0,
            allow_extrapolation=False,
        )
        self.assertEqual([round(item.minutes / (24 * 60)) for item in selected], [25, 35])

    def test_record_rows_adds_metadata_and_reads_recent_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "records", "calculations.csv")
            rows = [
                {
                    "ts_utc": "2026-01-01T00:00:00+00:00",
                    "symbol": "SPY",
                    "status": "ok",
                    "asset_vix_30d": 18.5,
                },
                {
                    "ts_utc": "2026-01-01T00:01:00+00:00",
                    "symbol": "QQQ",
                    "status": "error",
                    "asset_vix_30d": None,
                },
            ]

            recorded = asset_vix.record_rows(path, rows, source="test", run_id="run123")
            self.assertTrue(os.path.exists(path))
            self.assertEqual(len(recorded), 2)
            self.assertEqual(recorded[0]["run_id"], "run123")
            self.assertEqual(recorded[0]["source"], "test")
            self.assertIn("recorded_at_utc", recorded[0])

            recent = asset_vix.read_recent_csv_rows(path, limit=1)
            self.assertEqual(len(recent), 1)
            self.assertEqual(recent[0]["symbol"], "QQQ")
            self.assertEqual(recent[0]["run_id"], "run123")

    def test_write_csv_rows_escapes_spreadsheet_formula_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "records.csv")
            rows = [
                {
                    "symbol": "SPY",
                    "status": "ok",
                    "reason": "=HYPERLINK(\"https://example.com\")",
                },
                {
                    "symbol": "QQQ",
                    "status": "ok",
                    "reason": "  +SUM(1,2)",
                },
                {
                    "symbol": "IWM",
                    "status": "ok",
                    "reason": "\t@cmd",
                },
            ]

            asset_vix.write_csv_rows(path, rows)
            recent = asset_vix.read_recent_csv_rows(path, limit=3)
            self.assertEqual(
                recent[0]["reason"],
                "'=HYPERLINK(\"https://example.com\")",
            )
            self.assertEqual(recent[1]["reason"], "'  +SUM(1,2)")
            self.assertEqual(recent[2]["reason"], "'\t@cmd")

    def test_synthetic_black_scholes_chain_produces_reasonable_vix(self):
        now = dt.datetime.now(asset_vix.ET_ZONE)
        expiry_dt = now + dt.timedelta(days=30)
        expiry = asset_vix.ExpiryChoice(
            expiration=expiry_dt.date().isoformat(),
            expiry_dt=expiry_dt,
            minutes=30 * 24 * 60,
            years=30 / 365,
        )
        quotes = []
        for strike in range(60, 141, 5):
            for side in ("call", "put"):
                mid = bs_price(100, strike, expiry.years, 0.04, 0.22, side)
                mid = max(mid, 0.01)
                quotes.append(
                    asset_vix.OptionQuote(
                        symbol=f"TST{strike}{side[0]}",
                        side=side,
                        strike=float(strike),
                        bid=max(mid - 0.01, 0.01),
                        ask=mid + 0.01,
                        mid=mid,
                        updated=None,
                        volume=None,
                        open_interest=None,
                        underlying_price=100,
                    )
                )

        term = asset_vix.compute_term_variance(
            expiration=expiry,
            quotes=quotes,
            rate=0.04,
            min_side_strikes=5,
        )
        vix_like = math.sqrt(asset_vix.interpolate_variance([term], 30)) * 100
        self.assertGreater(vix_like, 15)
        self.assertLess(vix_like, 35)


if __name__ == "__main__":
    unittest.main()
