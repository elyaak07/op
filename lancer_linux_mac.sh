#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -f .venv/bin/python ]; then
  python3 -m venv .venv
fi
if [ ! -f .venv/installation_ok ]; then
  .venv/bin/python -m pip install -r requirements.txt
  touch .venv/installation_ok
fi
.venv/bin/python -m streamlit run app.py
