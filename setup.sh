#!/usr/bin/env bash
# Sets up the virtual environment and dependencies.
# Usage: bash setup.sh
set -e

echo ">> Creating the venv (.venv)..."
python3 -m venv .venv

echo ">> Activating and upgrading pip..."
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip

echo ">> Installing dependencies..."
pip install -r requirements.txt

if [ ! -f .env ]; then
    echo ">> Creating the .env file from .env.example..."
    cp .env.example .env
    echo "   /!\\ Edit .env to fill in your Tuya credentials."
fi

echo ""
echo "Done. To use the project:"
echo "  source .venv/bin/activate"
echo "  python extract_tuya_consumption.py"
