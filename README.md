# AssetVIX

AssetVIX is a local web application and command-line tool for calculating a
VIX-like 30-day option-implied volatility value for optionable US equities and
ETFs.

The app uses MarketData.app option-chain data, US Treasury yield-curve data, and
a model-free variance calculation inspired by the Cboe VIX methodology. It is
designed for research, monitoring, and prototyping rather than for publishing an
official index.

> AssetVIX is not the official Cboe VIX. The official VIX is a proprietary Cboe
> index based on specific SPX/SPXW option inputs and index-governance rules.

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
- Stale quote diagnostics
- Per-symbol failure reasons instead of silently publishing bad values
- CSV output for scheduled runs and downstream analysis

## How It Works

For each symbol, AssetVIX:

1. Loads available option expirations from MarketData.app.
2. Selects expiration terms around the 30-day target horizon.
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
git clone https://github.com/Kevin57890/asset-vix.git
cd asset-vix
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

## Command-Line Usage

Single-symbol test:

```bash
python3 asset_vix.py --symbols SPY --mode delayed --allow-stale
```

Core liquid universe:

```bash
python3 asset_vix.py \
  --universe core \
  --mode delayed \
  --csv results.csv
```

Run every five minutes:

```bash
python3 asset_vix.py \
  --universe core \
  --mode delayed \
  --csv results.csv \
  --watch \
  --interval-seconds 300
```

You can also provide the token through the shell:

```bash
export MARKETDATA_TOKEN="your_marketdata_token_here"
```

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
code.

## Web App Controls

- **Symbols**: comma-, space-, or newline-separated ticker symbols.
- **Data mode**: `delayed`, `cached`, or `live`, depending on the
  MarketData.app plan.
- **Fallback**: optional retry mode when cached data is unavailable.
- **Strike limit**: maximum number of strikes requested per expiration.
- **Quote age**: maximum accepted quote age before the row is marked stale.
- **Max spread %**: filters quotes with very wide bid/ask spreads.
- **Delay sec**: adds a small delay between symbols to reduce bursty API calls.
- **Allow stale quotes with warning**: keeps stale rows but marks them clearly.
- **Allow expiration extrapolation**: uses the nearest expirations when the
  available expirations do not bracket the 30-day target.

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

## License

MIT License. See `LICENSE`.
