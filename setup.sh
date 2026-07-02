#!/usr/bin/env bash
# Installation de l'environnement virtuel et des dépendances.
# Usage :  bash setup.sh
set -e

echo ">> Création du venv (.venv)..."
python3 -m venv .venv

echo ">> Activation et mise à jour de pip..."
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip

echo ">> Installation des dépendances..."
pip install -r requirements.txt

if [ ! -f .env ]; then
    echo ">> Création du fichier .env depuis .env.example..."
    cp .env.example .env
    echo "   /!\\ Éditez .env pour renseigner vos identifiants Tuya."
fi

echo ""
echo "Terminé. Pour utiliser le projet :"
echo "  source .venv/bin/activate"
echo "  python extraction_conso_tuya.py"
