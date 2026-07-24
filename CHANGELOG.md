# Changelog

All notable project changes are summarized here.

## Unreleased

- Reworked the GitHub README homepage so the formula section uses stable
  plain-text notation instead of Markdown math blocks.

## 1.17.0 - 2026-07-24

- Added one-click Risk Lens presets for early watch, balanced monitoring, and
  stress events. Lenses update the Risk Pulse interpretation immediately, with
  no new market-data request.
- Carried the active lens into copied Risk Pulse and Run Brief text so handoffs
  preserve the alert stance as well as the exact thresholds.
- Refined the Risk Pulse tool strip with a compact, high-contrast preset
  control that keeps precise inputs available for custom rules.

## 1.16.0 - 2026-07-21

- Added a browser-local Signal Queue that collects symbols meeting the current
  Risk Pulse rules and can load them into the Symbols field for a deliberate
  follow-up scan.
- Kept queue loading non-executing: auto refresh pauses and the user still
  explicitly clicks Calculate before any market-data request begins.
- Added a warm, low-noise queue card and matching Run Brief action, then
  refreshed the GitHub preview to show the monitoring handoff workflow.

## 1.15.0 - 2026-07-21

- Added a one-click Run Brief that turns the current calculation into a concise,
  copyable research handoff: priority Risk Pulse signals, data-quality review,
  configured rules, visible-focus state, and the complete reading list.
- Kept Run Briefs entirely browser-local and derived from the existing run, so
  they do not send another market-data request or include tokens or local
  history.
- Added a polished briefing layer between the selected reading and results table
  and refreshed the GitHub preview to make the handoff workflow visible.

## 1.14.0 - 2026-07-18

- Added a browser-saved Results Focus control for isolating actionable Risk
  Pulse signals, data warnings/errors, or symbols whose historical baseline is
  still building—without an additional market-data request.
- Kept the complete run summary, Scanner, and exports visible while focusing
  the detailed table, so triage never loses the broader basket context.
- Refined the Results toolbar with a compact focus selector and refreshed the
  GitHub preview to show the prioritization workflow.

## 1.13.0 - 2026-07-16

- Added browser-saved Research Profiles for returning to a complete scan setup:
  symbols, data mode, quote-quality controls, and Risk Pulse rules are stored
  locally while MarketData.app Tokens remain excluded.
- Made profile loading intentionally non-executing and pause active monitoring
  until the user clicks Calculate, preventing accidental market-data requests
  after a context switch.
- Added a refined local-profile panel to the research basket controls and
  refreshed the GitHub preview to surface the reusable-workflow layer.

## 1.12.0 - 2026-07-15

- Added one-click, reproducible research-setup links that restore symbols,
  data mode, quote-quality controls, and Risk Pulse rules without starting a
  market-data request.
- Kept setup links deliberately non-sensitive: they exclude MarketData.app
  tokens, calculation results, and browser-local history.
- Added a compact setup-sharing control to the research basket panel and
  refreshed the GitHub preview to show the new collaboration workflow.

## 1.11.0 - 2026-07-15

- Added editable, browser-saved Risk Pulse thresholds for absolute AssetVIX
  level and percentage move alerts; the panel updates immediately without a
  second market-data query.
- Added a one-click, plain-text Risk Pulse brief for research notes and team
  updates, including the configured rules and prioritized signals.
- Refined the Risk Pulse header into a compact monitoring tool strip and
  refreshed the GitHub preview to show threshold-driven alerts in context.

## 1.10.0 - 2026-07-14

- Added per-symbol historical-baseline context to each new calculation: usable
  sample count, median, percentile, and high/normal/low regime labels.
- Require at least three prior usable observations before assigning a regime,
  so sparse history remains explicitly marked as a baseline in progress.
- Added a Risk Pulse panel that prioritizes elevated historical readings and
  sharp run-to-run moves, with direct selection into the detailed result view.
- Refined the dashboard hierarchy and refreshed the GitHub preview to surface
  the new monitoring signal layer without making the result table harder to scan.

## 1.9.0 - 2026-07-14

- Added a previous-run comparison for every calculated symbol, surfacing the
  absolute and percentage change from its latest usable local record.
- Kept comparison fields scoped to the current run response and export, so
  existing long-term calculation-history CSV files remain clean and compatible.
- Redesigned the local dashboard with a dark research-terminal result stage,
  softer data surfaces, clearer hierarchy, and stronger visual feedback for
  volatility moves.
- Added a dedicated “vs Prior” results column and hero-level change indicator
  so monitoring changes are readable at a glance.

## 1.8.0 - 2026-07-13

- Added a Volatility Scanner to rank the current calculation basket by 30-day
  AssetVIX, including high/low values, basket spread, and deviation from the
  basket average.
- Added persistent result sorting by high-to-low volatility, low-to-high
  volatility, or symbol.
- Made scanner entries interactive so selecting one updates the detailed
  result panel without running a new query.

## 1.7.0 - 2026-07-13

- Added opt-in 5/15/30/60-minute auto refresh for local monitoring sessions.
- Added a visible next-run countdown and explicit running/paused states.
- Paused auto refresh when the app tab is hidden and resumed scheduling when it
  becomes visible again, avoiding background token and request consumption.
- Refreshed the controls panel with a dedicated monitoring card.

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
