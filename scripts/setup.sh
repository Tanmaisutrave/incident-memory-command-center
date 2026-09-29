#!/usr/bin/env bash
# setup.sh — bash equivalent of setup.ps1
# Usage: bash scripts/setup.sh
set -euo pipefail
cd "$(dirname "$0")/.."

ENV_FILE="backend/.env"
EXAMPLE_FILE="backend/.env.example"

echo ""
echo "============================================================"
echo "  Incident Memory Agent — Environment Setup"
echo "============================================================"
echo ""

if [[ -f "$ENV_FILE" ]]; then
  echo "[!] $ENV_FILE already exists."
  read -rp "Overwrite it? (y/N) " overwrite
  if [[ "${overwrite,,}" == "y" ]]; then
    cp "$EXAMPLE_FILE" "$ENV_FILE"
    echo "[+] Created new .env from template."
  else
    echo "[*] Keeping existing .env."
  fi
else
  cp "$EXAMPLE_FILE" "$ENV_FILE"
  echo "[+] Created .env from template."
fi

echo ""
echo "You need two API keys:"
echo "  1. Hindsight API Key  — https://hindsight.vectorize.io/"
echo "  2. Groq API Key       — https://console.groq.com/"
echo ""

read -rp "Configure API keys now? (Y/n) " configure
if [[ "${configure,,}" != "n" ]]; then
  # Read without echoing
  read -rsp "Hindsight API Key: " HINDSIGHT_KEY; echo ""
  read -rsp "Groq API Key: "      GROQ_KEY;      echo ""

  if [[ -n "$HINDSIGHT_KEY" && -n "$GROQ_KEY" ]]; then
    # String-literal replacement — no regex
    TMP=$(mktemp)
    while IFS= read -r line; do
      if [[ "$line" == "HINDSIGHT_API_KEY=your_hindsight_api_key_here" ]]; then
        echo "HINDSIGHT_API_KEY=$HINDSIGHT_KEY"
      elif [[ "$line" == "GROQ_API_KEY=your_groq_api_key_here" ]]; then
        echo "GROQ_API_KEY=$GROQ_KEY"
      else
        echo "$line"
      fi
    done < "$ENV_FILE" > "$TMP"
    mv "$TMP" "$ENV_FILE"
    echo "[+] API keys written to $ENV_FILE"
  else
    echo "[!] One or both keys were empty — skipped."
  fi

  read -rp "Generate a random APP_API_KEY? (y/N) " genkey
  if [[ "${genkey,,}" == "y" ]]; then
    APP_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    TMP=$(mktemp)
    while IFS= read -r line; do
      if [[ "$line" == "APP_API_KEY=" ]]; then
        echo "APP_API_KEY=$APP_KEY"
      else
        echo "$line"
      fi
    done < "$ENV_FILE" > "$TMP"
    mv "$TMP" "$ENV_FILE"
    echo "[+] APP_API_KEY written to $ENV_FILE"
  fi
else
  echo "[*] Edit $ENV_FILE manually to add your API keys."
fi

echo ""
echo "Next steps:"
echo "  python -m venv .venv"
echo "  source .venv/bin/activate"
echo "  pip install -r backend/requirements.txt -r backend/requirements-dev.txt"
echo "  cd frontend && npm ci --legacy-peer-deps && node build.mjs && cd .."
echo "  bash scripts/run.sh"
echo ""
