# Recall — Incident Memory Command Center

An incident-response assistant that remembers verified outcomes and failed attempts, then tests that experience against the next incident's evidence. Built with React, FastAPI, Groq and Hindsight.

## Run the prepared project

From this folder in PowerShell: `./run.ps1`. Open http://127.0.0.1:8000.
Use `./run.ps1 -Rebuild` after frontend edits. Stop an existing instance with Ctrl+C before restarting. This is a local, single-team prototype; public hosting requires authentication, authorization and request limits first.

## First setup on another machine

Requires Python 3.11+ and Node.js 20+.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env
cd frontend
npm ci
npm run build
cd ..
./run.ps1
```

Edit `backend/.env` privately. Set `GROQ_API_KEY`, `HINDSIGHT_API_KEY`, `HINDSIGHT_BASE_URL=https://api.hindsight.vectorize.io`, and a dedicated `HINDSIGHT_BANK_ID`. The default Groq model is `openai/gpt-oss-120b`. Keys never go in frontend code or Git. Existing local keys are already configured in this prepared copy.

Without keys, the app opens in setup mode and offers a clearly labelled static walkthrough. Live recommendations require Groq; memory requires Hindsight. An unavailable memory service is disclosed and analysis can continue using current evidence. A failed model response produces an error, never a fabricated diagnosis.

## A one-minute demo

See [the demo script](docs/DEMO_SCRIPT.md). The prepared bank has one explicitly synthetic resolved Redis incident. The local timeline also preserves the original checkout's records; imported records are not automatically uploaded to Hindsight.

1. **Memory comparison:** choose Recurring Redis timeout and compare the same input with and without history. Open the cited fragments and show exactly what history contributed.
2. **Incident workspace:** choose Same symptom, new cause. The old pool fix should be challenged by low pool wait and current packet loss.
3. **Add what happened next:** record an unsuccessful attempt, re-analyze, and verify the recommendation accounts for it.
4. **Record outcome:** choose resolved, mitigated or escalated. Local persistence and remote memory delivery are separate; a failed delivery exposes a retry button.
5. **Memory explorer / Learning journal:** retrieve recorded experience or request a Hindsight reflection.

These are model-generated hypotheses for human review, not automatic remediation. Source identifiers prove retrieval provenance, not factual correctness. Confirm the suggested checks and recovery signals.

## What changed

- Responsive slate-and-mint UI with visible evidence, actual request timings, source details and recoverable errors.
- Real memory-on/off comparison, run concurrently with the same model and instructions.
- Groq strict structured responses with local validation, known-source checks, explicit uncertainty, disconfirming checks and recovery criteria. Removed hard-coded diagnosis and invented confidence scores.
- SQLite persistence for incidents, analysis and updates. Memory delivery is reported only after provider acknowledgment; partial and escalated outcomes retain their actual status.
- No artificial loading delays, bounded provider calls, capped retrieval and one model call per analysis. Past model answers are excluded from fresh analysis input.

## Verify

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q -p no:cacheprovider
cd frontend
npm run build
```

Tests run offline without provider usage. Live tests consume provider quota and should use synthetic data in a dedicated bank. The saved live result in `docs/live-verification.json` is a real synthetic test output; it is not a canned API response. Timing is one observed run, not a benchmark or latency guarantee.

## Storage and operation

- `backend/.env`: private credentials, ignored by Git.
- `backend/data/incidents.sqlite3`: local durable records, ignored by Git. Back up this file to preserve the workspace.
- Hindsight bank: remote memory; separate from the SQLite list. Retrying a save uses the incident's stable document ID.
- `frontend/dist`: generated assets served by FastAPI. API documentation: http://127.0.0.1:8000/docs.
- Counters for successful recalls/retains are session counters; dashboard incident totals come from local persisted records.

No infrastructure actions, messages, public deployment or Git push are performed by this app. Logs and incident text supplied for analysis are sent to the configured AI/memory providers; use synthetic or appropriately redacted inputs.

Provider format reference: [Groq structured outputs](https://console.groq.com/docs/structured-outputs). Schema compliance controls format; it does not establish that a diagnosis or suggested threshold is correct. Review all recommendations against actual telemetry.
