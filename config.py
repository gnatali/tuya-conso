# -*- coding: utf-8 -*-
"""
config.py -- chargement de la configuration depuis .env, avec surcharge
possible par tinytuya.json (généré par `python -m tinytuya wizard`).
"""

import os
import sys
import json
import datetime as dt
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # charge .env s'il existe

_TINYTUYA_JSON = Path(__file__).resolve().parent / "tinytuya.json"


def _requis(nom):
    val = os.getenv(nom, "").strip()
    if not val or val.startswith("VOTRE_"):
        sys.exit(
            f"[config] La variable {nom} n'est pas renseignée.\n"
            f"          Copiez .env.example en .env et complétez-le :\n"
            f"          cp .env.example .env"
        )
    return val


def _charger_tinytuya_json():
    if not _TINYTUYA_JSON.exists():
        return None
    try:
        with open(_TINYTUYA_JSON, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"[config] {_TINYTUYA_JSON.name} illisible : {e}")


_wizard = _charger_tinytuya_json()

if _wizard:
    # tinytuya.json (issu de `python -m tinytuya wizard`) prend le pas sur .env
    print(f"[config] {_TINYTUYA_JSON.name} détecté -> utilisé à la place de .env "
          f"pour la connexion (région/clés/device).")
    API_REGION = (_wizard.get("apiRegion") or "eu").strip()
    API_KEY = (_wizard.get("apiKey") or "").strip()
    API_SECRET = (_wizard.get("apiSecret") or "").strip()
    DEVICE_ID = (_wizard.get("apiDeviceID") or "").strip()
    if not (API_KEY and API_SECRET and DEVICE_ID):
        sys.exit(
            f"[config] {_TINYTUYA_JSON.name} incomplet (apiKey/apiSecret/apiDeviceID "
            f"requis). Relancez : python -m tinytuya wizard"
        )
else:
    API_REGION = os.getenv("TUYA_API_REGION", "eu").strip() or "eu"
    API_KEY = _requis("TUYA_API_KEY")
    API_SECRET = _requis("TUYA_API_SECRET")
    DEVICE_ID = _requis("TUYA_DEVICE_ID")

# Date d'installation
_install = os.getenv("INSTALL_DATE", "2022-01-01").strip()
try:
    DATE_INSTALLATION = dt.datetime.strptime(_install, "%Y-%m-%d").date()
except ValueError:
    sys.exit(f"[config] INSTALL_DATE invalide : '{_install}' (attendu AAAA-MM-JJ)")

# Code énergie (None = détection automatique)
_code = os.getenv("CODE_ENERGIE", "").strip()
CODE_ENERGIE = _code if _code else None

# Fichiers de sortie
CSV_JOUR = "historique_conso_journalier.csv"
CSV_MOIS = "historique_conso_mensuel.csv"
