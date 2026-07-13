# Changelog

All notable project changes are summarized here.

## Unreleased

- Reworked the GitHub README homepage so the formula section uses stable
  plain-text notation instead of Markdown math blocks.

## 1.6.0 - 2026-07-12

- Added rolling 7-day, 30-day, 90-day, and 12-month windows to history,
  time-series data, and filtered history exports.
- Added median, period-over-period percentage change, current percentile, and
  low/normal/high regime labels to history analytics.
- Redesigned the History panel as a monitoring dashboard with an explicit time
  window selector and expanded analytics cards.
- Added regression coverage for rolling-window filtering and regime analytics.

## 1.5.0 - 2026-07-10

- Added a filtered history analytics API for latest, previous, change, average,
  low, high, and numeric sample counts.
- Added a History Analytics summary strip to the web app so selected history
  filters show trend context without exporting data.
- Refreshed the GitHub README showcase screenshot for the expanded history
  analysis workflow.

## 1.4.0 - 2026-07-09

- Added filtered history CSV and JSON exports that respect the selected symbol
  and status filters.
- Added a current-run summary strip for OK, warning, error, and average 30-day
  values.
- Refreshed the GitHub README showcase screenshot for the expanded export
  workflow.

## 1.3.0 - 2026-07-08

- Added browser-saved custom symbol lists for recurring research baskets.
- Added current-run CSV and JSON exports from the results table.
- Added symbol and status filters to the local history API, with counts for
  matched and total records.
- Refreshed the GitHub README showcase screenshot for the expanded interface.

- Added a README usage preview section with a web-app screenshot and quick-start
  commands for GitHub visitors.

## 1.2.0 - 2026-07-06

- Added web controls for a manual risk-free rate and minimum strike depth.
- Added history filtering by symbol and result status.
- Added browser-side persistence for non-sensitive query settings.
- Added `--fail-on-non-ok` for CLI and scheduled-job integration.
- Added regression coverage for strict CLI exit codes and the new quality
  controls.

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
