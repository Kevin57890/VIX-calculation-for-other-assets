# Contributing to AssetVIX

Thanks for improving AssetVIX. This project is intentionally small and
local-first, so contributions should keep the setup simple and avoid adding
dependencies unless there is a clear reliability or correctness reason.

## Development Setup

Use Python 3.9 or newer:

```bash
git clone https://github.com/Kevin57890/VIX-calculation-for-other-assets.git
cd VIX-calculation-for-other-assets
python3 -m unittest test_asset_vix.py test_server_token.py
```

The app has no required third-party Python packages. `requirements.txt` is
intentionally empty for deployment tools that expect the file.

GitHub Actions runs source compilation and the unit suite on Python 3.9 and
3.13. Local changes should pass the same checks before they are pushed.

## Local App Checks

Run the browser app locally:

```bash
python3 run.py
```

The server binds to `127.0.0.1` and stores a saved MarketData.app token in the
local `.env` file. Do not commit `.env`, `records/`, or downloaded result files.

## Change Guidelines

- Keep formula changes small and testable.
- Prefer standard-library code unless a dependency removes substantial risk.
- Preserve per-symbol error rows for batch runs.
- Treat token handling, CSV export, and local HTTP boundaries as security-sensitive.
- Add or update tests for each bug fix.

## Pull Request Checklist

Before opening a pull request or pushing a change:

- Run `python3 -m unittest test_asset_vix.py test_server_token.py`.
- Confirm `git status --short` only shows intended files.
- Avoid committing local calculation records, API tokens, caches, or screenshots.
- Document user-facing behavior changes in `README.md` or `CHANGELOG.md`.
