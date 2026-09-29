# Verification — 29 September 2026

- Offline regression suite: **21 passed**. Includes invalid model output, invented sources, unavailable memory, durable outcomes, unsuccessful delivery, reopened evidence, concurrent comparison and strict provider schema configuration.
- Production frontend build: passed. Bundle approximately 184 KB JavaScript (58 KB gzip).
- Browser: inspected overview, form and live comparison; navigation labels available to assistive technology. Checked narrow viewport and final browser error log (no errors).
- Live Hindsight: synthetic outcome retained; later failed pool increase retained and retrieved. Reflection endpoint returned successfully.
- Live Groq: current evidence changed the diagnosis from historical pool exhaustion to network degradation. After recording the failed pool increase, the final strict-schema analysis completed in 8.1 seconds (2.1 seconds recall / 6.0 seconds model). Saved in live-verification.json.
- Earlier live comparison: 3.1 seconds without memory, 5.7 seconds with memory; five source fragments cited. These are individual observations, not benchmarks.
- Local restart via run.ps1 succeeded; persisted incidents survived restart.
- Git: credentials ignored and untracked; no push or public deployment.

Known limits: provider-generated advice can still include unsupported assumptions or suggested targets. Source validation checks identifiers, not semantic truth. Treat diagnoses and remediation as unconfirmed, review against telemetry, and perform a broader labeled evaluation before operational use. The prototype is intended for a local single-team demo; public hosting requires access controls and request limits.
