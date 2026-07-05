# Changelog

All notable project changes are summarized here.

## Unreleased

## 1.1.0 - 2026-07-05

- Added optional minimum open-interest and volume filters to browser queries.
- Added a versioned JSON export for complete calculation history.
- Added a confirmed in-app action for clearing local calculation history.
- Added regression coverage for liquidity filters, JSON exports, and history
  cleanup.
- Extended CI to validate browser JavaScript syntax.

## 1.0.0 - 2026-07-04

- Added local web app and CLI for VIX-style 30-day implied-volatility
  calculations on optionable US equities and ETFs.
- Added preset symbol universes, automatic calculation records, and a browser
  time-series chart.
- Hardened token handling, request validation, local server boundaries, CSV
  exports, records downloads, universe loading, and JSON request parsing.
- Added project maintenance files: contributing guide, security policy, and
  changelog.
- Added synchronized in-process CSV history reads and writes for concurrent web
  requests.
- Added strict CLI numeric validation and a 100-symbol browser-query limit.
- Added consistent browser security headers and generic internal-error
  responses.
- Added GitHub Actions CI for Python 3.9 and 3.13.

## Notes

AssetVIX is not an official Cboe index implementation. It follows the public
VIX-style formula structure for research and monitoring workflows.
