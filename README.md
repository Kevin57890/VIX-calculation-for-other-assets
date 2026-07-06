# AssetVIX

[![CI](https://github.com/Kevin57890/VIX-calculation-for-other-assets/actions/workflows/ci.yml/badge.svg)](https://github.com/Kevin57890/VIX-calculation-for-other-assets/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Kevin57890/VIX-calculation-for-other-assets)](https://github.com/Kevin57890/VIX-calculation-for-other-assets/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

AssetVIX is a local web application and command-line tool for calculating a
VIX-style 30-day option-implied volatility value for optionable US equities and
ETFs.

The app uses MarketData.app option-chain data, US Treasury yield-curve data, and
the public SPX VIX formula structure: forward-price estimation from put-call
parity, `K0` selection, out-of-the-money option selection, single-term variance,
and 30-day variance interpolation. It is designed for research, monitoring, and
prototyping rather than for publishing an official index.

> AssetVIX is not the official Cboe VIX. The official VIX is a proprietary Cboe
> index based on specific SPX/SPXW option inputs and index-governance rules.

## Project Status

AssetVIX is a local-first research tool. The repository is intended to be usable
from a fresh clone: it includes the local web app, CLI, preset symbol universes,
unit tests, contribution notes, security guidance, and a changelog.

Maintenance files:

- [Contributing guide](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Changelog](CHANGELOG.md)

## Highlights

- Local browser-based UI
- Command-line batch mode
- Works with user-provided MarketData.app API tokens
- Token validation before saving
- No third-party Python dependencies
- Preset symbol universes for liquid ETFs and large-cap equities
- 30-day variance interpolation
- Treasury yield-curve based risk-free-rate interpolation
- Bid/ask midpoint option pricing
- Wide-spread quote filtering
- Minimum option volume and open-interest filters in the web app
- Manual risk-free-rate override and minimum strike-depth control
- Stale quote diagnostics
- Per-symbol failure reasons instead of silently publishing bad values
- Automatic local CSV records for every calculation
- Browser time-series chart built from recorded AssetVIX points
- CSV and JSON history exports with an in-app clear action
- History filtering by symbol and result status
- Automatic browser-side memory for non-sensitive query settings
- Thread-safe in-process calculation history writes
- Automated CI checks across supported Python versions

## Formula

For each selected expiration, AssetVIX estimates the forward level:

```text
F = K + exp(RT) * (Call(K) - Put(K))
```

where `K` is the strike with the smallest absolute call/put price difference.

`K0` is the highest strike less than or equal to `F`.

For each selected strike, the app uses:

- OTM puts when `K < K0`
- the average of call and put midpoints when `K = K0`
- OTM calls when `K > K0`

The strike interval is:

```text
DeltaK(i) = K(i+1) - K(i)                    for the first strike
DeltaK(i) = (K(i+1) - K(i-1)) / 2            for interior strikes
DeltaK(i) = K(i) - K(i-1)                    for the last strike
```

Single-term variance is:

```text
sigma^2 = (2 / T) * sum[DeltaK / K^2 * exp(RT) * Q(K)]
          - (1 / T) * (F / K0 - 1)^2
```

The final 30-day value is the square root of the interpolated 30-day variance:

```text
AssetVIX = 100 * sqrt(variance_30d)
```

By default, the app uses the SPX VIX-style expiration window of 23 to 37 days
around the 30-day target.

## How It Works

For each symbol, AssetVIX:

1. Loads available option expirations from MarketData.app.
2. Selects expiration terms around the 30-day target horizon, defaulting to the
   23-37 day VIX-style window.
3. Loads option chains for the selected expirations.
4. Uses call/put parity to estimate the forward level.
5. Selects the strike at or below the forward level as `K0`.
6. Uses out-of-the-money puts and calls for variance contribution.
7. Applies quote-quality filters and zero-bid stopping logic.
8. Computes term variance.
9. Interpolates to a 30-day target horizon.
10. Returns `AssetVIX = sqrt(30-day variance) * 100`.

The output includes diagnostic fields such as selected expirations, forward
levels, `K0`, strike counts, quote age, and failure reasons.

## Requirements

- Python 3.9 or newer
- Internet access
- A MarketData.app API token with access to:
  - US stock quote endpoints
  - US option expiration and option-chain endpoints

No external Python packages are required. The project uses only the Python
standard library.

## Installation

Download or clone the repository:

```bash
git clone https://github.com/Kevin57890/VIX-calculation-for-other-assets.git
cd VIX-calculation-for-other-assets
```

Optional, but safe for deployment tools:

```bash
pip install -r requirements.txt
```

`requirements.txt` is intentionally empty because the app has no third-party
dependencies.

## Get a MarketData.app API Token

1. Sign in to [MarketData.app](https://www.marketdata.app/).
2. Open the account or customer dashboard.
3. Find the API token or request-token section.
4. Generate a token.
5. Keep the token private.

Only paste the token value into the app. Do not paste command snippets such as:

```text
Bearer ...
MARKETDATA_TOKEN=...
export MARKETDATA_TOKEN=...
```

The app tries to clean common paste formats, but using the raw token is safest.

## Run the Local Web App

From the repository directory:

```bash
python3 run.py
```

If your system uses `python` instead of `python3`:

```bash
python run.py
```

The terminal prints a local URL, usually:

```text
http://127.0.0.1:8765/
```

Open the URL in a browser. Click **Add Token**, paste your MarketData.app token,
and save it. The app validates the token against both a stock quote endpoint and
an option-expiration endpoint before saving it.

The token is stored locally in `.env`, which is ignored by Git.

Check the installed project version with:

```bash
python3 asset_vix.py --version
```

## Command-Line Usage

Single-symbol test:

```bash
python3 asset_vix.py --symbols SPY --mode delayed --allow-stale
```

Core liquid universe:

```bash
python3 asset_vix.py \
  --universe core \
  --mode delayed
```

Run every five minutes:

```bash
python3 asset_vix.py \
  --universe core \
  --mode delayed \
  --watch \
  --interval-seconds 300
```

Each command-line calculation is recorded by default. To write to a custom
record file:

```bash
python3 asset_vix.py --symbols SPY,QQQ --csv records/custom.csv
```

To run without recording:

```bash
python3 asset_vix.py --symbols SPY --no-record
```

For scripts and scheduled jobs, return exit status `1` when any symbol is not
`ok`:

```bash
python3 asset_vix.py \
  --symbols SPY,QQQ \
  --json \
  --fail-on-non-ok
```

You can also provide the token through the shell:

```bash
export MARKETDATA_TOKEN="your_marketdata_token_here"
```

## Automatic Records

The web app and command-line tool append every calculation to:

```text
records/calculations.csv
```

The file is created automatically on the first calculation. Each saved row
includes `recorded_at_utc`, `run_id`, and `source` fields in addition to the
calculation diagnostics.

In the web app, the **Time Series** chart connects recorded AssetVIX values by
record time. The chart can show all recorded symbols or one selected symbol. The
**History** table shows the latest recorded rows after every query. Use
**Download CSV** or **Download JSON** to export the full local record file. Use
the symbol and status controls to filter displayed rows. Use **Clear History**
to remove the local record file after confirmation.

The `records/` directory is ignored by Git so downloaded copies of this project
do not publish local calculation history.

## Preset Universes

Preset symbols are stored in `universes.csv`.

Useful groups include:

- `core`
- `etfs`
- `mega_cap`
- `semis`
- `liquid50`
- `liquid100`

Edit `universes.csv` to add or remove symbols without changing application
code. A single browser query accepts up to 100 unique symbols to prevent
accidental long-running requests and unexpected API-credit usage.

## Web App Controls

- **Symbols**: comma-, space-, or newline-separated ticker symbols.
- **Data mode**: `delayed`, `cached`, or `live`, depending on the
  MarketData.app plan.
- **Fallback**: optional retry mode when cached data is unavailable.
- **Strike limit**: maximum number of strikes requested per expiration.
- **Min open interest**: optional server-side option-chain liquidity filter.
- **Min volume**: optional server-side option-chain activity filter.
- **Manual rate %**: optional annualized risk-free rate override; blank uses the
  Treasury curve.
- **Min side strikes**: minimum usable out-of-the-money puts and calls required
  for each term.
- **Quote age**: maximum accepted quote age before the row is marked stale.
- **Max spread %**: filters quotes with very wide bid/ask spreads.
- **Delay sec**: adds a small delay between symbols to reduce bursty API calls.
- **Allow stale quotes with warning**: keeps stale rows but marks them clearly.
- **Allow expiration extrapolation**: uses the nearest expirations when the
  available expirations do not bracket the 30-day target.
- **Time Series**: plots recorded numeric AssetVIX points over time from the
  local records file.
- **History actions**: refresh, export as CSV or JSON, or clear local records.

The browser remembers symbols, data mode, quality filters, and toggles locally
between sessions. API tokens are not stored in browser storage.

## Methodology Boundaries

The formula implementation follows the public SPX VIX mathematics. Exact
official VIX replication also depends on Cboe's official SPX/SPXW input data,
settlement conventions, filtering rules, dissemination rules, and index
governance. AssetVIX can produce a VIX-style value for arbitrary optionable
symbols, but those values are not official exchange indices.

## References

- [Cboe Volatility Index Methodology](https://cdn.cboe.com/resources/indices/Volatility_Index_Methodology_Cboe_Volatility_Index.pdf)
- [Cboe Volatility Index Mathematics Methodology](https://cdn.cboe.com/resources/indices/Cboe_Volatility_Index_Mathematics_Methodology.pdf)
- [MarketData.app API Documentation](https://www.marketdata.app/docs/api/)

## Output Fields

Common output fields include:

- `ts_utc`: calculation timestamp
- `symbol`: underlying symbol
- `status`: `ok`, `error`, or a warning status
- `asset_vix_30d`: 30-day VIX-like value
- `variance_30d`: interpolated 30-day variance
- `expirations`: selected expiration dates
- `days`: time to selected expirations
- `rates`: interpolated risk-free rates
- `forwards`: estimated forward levels
- `k0`: selected `K0` strikes
- `strike_counts`: number of strikes used in each term calculation
- `max_quote_age_minutes`: maximum quote age observed
- `reason`: diagnostic reason when the row is not valid

## Reliability Rules

Only treat `status = ok` as a fresh publishable value.

For any other status, store the row as a diagnostic. A downstream system should
keep the last valid value or mark the symbol unavailable instead of publishing a
new number.

Common non-publishable cases:

- invalid or insufficient MarketData.app plan
- stale quotes
- too few usable out-of-the-money calls or puts
- missing expiration terms
- wide or crossed bid/ask quotes
- temporary MarketData.app or network errors

## Data and Methodology Notes

AssetVIX depends on option-chain quality. Thin symbols, stale quotes, or wide
spreads can produce unstable values. The app is intentionally conservative: it
returns diagnostics instead of forcing a number when the input data is not good
enough.

For individual equities, early exercise, dividends, corporate actions, and
option adjustments may affect results. This app is a practical monitoring tool,
not an exchange-governed index engine.

## Security

Do not commit or distribute local runtime files:

- `.env`
- `results.csv`
- `records/`
- `__pycache__/`
- `.pytest_cache/`

These files are ignored by `.gitignore`.

If an API token is ever pasted into a public issue, chat, commit, or screenshot,
rotate it in the MarketData.app dashboard.

## Tests

Run the local unit tests:

```bash
python3 -m unittest test_asset_vix.py test_server_token.py
```

GitHub Actions runs the same suite plus source compilation on Python 3.9 and
3.13 for every push to `main` and every pull request.

## License

MIT License. See `LICENSE`.
