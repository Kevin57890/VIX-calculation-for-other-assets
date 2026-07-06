# Security Policy

AssetVIX is a local research tool that works with user-provided
MarketData.app API tokens. The project does not operate a hosted service.

## Supported Versions

Security fixes target the `main` branch.

## Reporting a Vulnerability

If you find a vulnerability, avoid posting API tokens, private records, or
exploit details in a public issue. Use GitHub private vulnerability reporting if
it is available for this repository. If private reporting is not available, open
a minimal public issue that describes the affected area without secrets or
step-by-step exploit details.

Useful report details:

- affected file or endpoint
- expected behavior
- actual behavior
- local reproduction steps without real API tokens
- impact on local tokens, records, calculations, or exported CSV files

## Token Safety

Never commit or share:

- `.env`
- MarketData.app API tokens
- `records/`
- downloaded CSV exports that contain private research history

If a token is exposed in a commit, screenshot, issue, chat, or log, rotate it in
the MarketData.app dashboard.

## Local Server Boundary

The web app is designed to bind to `127.0.0.1`. Do not expose it directly to a
public network. If you place the app behind another server, review Host, Origin,
token storage, and records download behavior first.

Local HTTP responses apply a restrictive Content Security Policy, deny framing,
disable unnecessary browser permissions, and avoid returning internal exception
details to the browser.

The browser remembers non-sensitive query settings in local storage. API tokens
remain in the server-side `.env` file or process environment and are never saved
to browser storage.
