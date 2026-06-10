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
    def test_unix_timestamp_normalization_accepts_seconds_and_millis(self):
        self.assertEqual(asset_vix._to_unix_seconds(1_700_000_000), 1_700_000_000)
        self.assertEqual(asset_vix._to_unix_seconds(1_700_000_000_000), 1_700_000_000)

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
