#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extraction_conso_tuya.py
------------------------
Extraction de l'historique de consommation d'un compteur Tuya (ex. PC321-W-TY)
depuis le service Statistiques du cloud Tuya, sans modifier l'installation.

Le service Statistiques agrège les données par jour / semaine / mois et les
conserve sur le long terme (c'est ce qui alimente la courbe de l'app Smart Life),
contrairement aux logs bruts limités a 7 jours.

Configuration : voir le fichier .env (modèle : .env.example).
Sorties :
    - historique_conso_journalier.csv   (date; kWh)
    - historique_conso_mensuel.csv      (mois; kWh)
"""

import csv
import sys
import datetime as dt

try:
    import tinytuya
except ImportError:
    sys.exit("TinyTuya n'est pas installé. Activez le venv puis :  pip install -r requirements.txt")

import config


# =============================================================================
# CONNEXION
# =============================================================================

def connexion():
    return tinytuya.Cloud(
        apiRegion=config.API_REGION,
        apiKey=config.API_KEY,
        apiSecret=config.API_SECRET,
        apiDeviceID=config.DEVICE_ID,
    )


def appel(cloud, url, query=None):
    """Appel signé GET. Renvoie 'result' ou lève une erreur explicite.

    Les paramètres de requête DOIVENT passer par `query` (dict), jamais être
    concaténés à la main dans `url` : Tuya signe la requête en triant les
    paramètres par ordre alphabétique de clé (nouvel algorithme de signature),
    et TinyTuya ne le fait que si `query` est un dict. Un ordre différent
    (ex. code/start_day/end_day au lieu de code/end_day/start_day) provoque un
    échec 1004 "sign invalid" — confirmé par test direct le 2026-07-02.
    """
    rep = cloud.cloudrequest(url, query=query)
    if not isinstance(rep, dict):
        raise RuntimeError(f"Réponse inattendue : {rep!r}")

    if rep.get("success"):
        return rep.get("result")

    code = rep.get("code")
    msg = rep.get("msg", "")
    aide = {
        1004: "Signature incorrecte : vérifiez ACCESS_ID / ACCESS_SECRET et la région.",
        1106: "Permission refusée : liez le compte app au projet (onglet Devices).",
        1010: "Token invalide ou expiré (TinyTuya le renouvelle normalement seul).",
        28841105: "API non autorisée : souscrivez/autorisez IoT Core + Smart Home Basic.",
        28841002: "Abonnement IoT Core expiré : prolongez la période d'essai.",
        2007: "Statistiques non activées pour ce produit (ticket PID/DP cote Tuya).",
        1108: "URI invalide : vérifiez le chemin de l'endpoint appelé.",
        28841101: "API non souscrite : souscrivez le service Statistiques (Cloud > Cloud Services) en plus de IoT Core / Smart Home Basic.",
    }.get(code, "")
    raise RuntimeError(f"Erreur Tuya {code} : {msg}. {aide}".strip())


# =============================================================================
# DÉCOUVERTE DU CODE ÉNERGIE
# =============================================================================

def detecter_grandeur(cloud):
    """Renvoie (code, stat_type) pour la grandeur "énergie".

    `stat_type` (ex. "minux") est renvoyé par /all-statistic-type pour
    chaque code et DOIT être repassé tel quel dans les appels
    /statistics/days et /statistics/months : sans lui, Tuya répond quand
    même success=True mais avec des valeurs à "0.00" pour toutes les dates
    (pas d'erreur explicite) — confirmé par test direct le 2026-07-02.
    """
    print(">> Détection des grandeurs statistiques disponibles...")
    res = appel(cloud, f"/v1.0/devices/{config.DEVICE_ID}/all-statistic-type")
    if not res:
        raise RuntimeError("Aucune statistique disponible pour cet appareil.")

    grandeurs = {
        item.get("code"): item.get("stat_type")
        for item in res if isinstance(item, dict) and item.get("code")
    }
    print("   Grandeurs trouvées :",
          ", ".join(f"{c} ({t})" for c, t in grandeurs.items()) or "(aucune)")

    if config.CODE_ENERGIE:
        if config.CODE_ENERGIE not in grandeurs:
            raise RuntimeError(
                f"CODE_ENERGIE={config.CODE_ENERGIE!r} introuvable parmi : "
                f"{list(grandeurs)}"
            )
        return config.CODE_ENERGIE, grandeurs[config.CODE_ENERGIE]

    for prefere in ("add_ele", "EnergyConsumed", "electricity",
                     "total_forward_energy", "forward_energy_total", "energy"):
        if prefere in grandeurs:
            print(f"   -> code d'énergie retenu : {prefere}")
            return prefere, grandeurs[prefere]

    for c, t in grandeurs.items():
        if c and ("ele" in c.lower() or "energy" in c.lower()):
            print(f"   -> code d'énergie deviné : {c}")
            return c, t

    raise RuntimeError(
        "Impossible d'identifier le code d'énergie automatiquement. "
        f"Choisissez-en un parmi : {list(grandeurs)} et renseignez CODE_ENERGIE dans .env."
    )


# =============================================================================
# EXTRACTION JOURNALIÈRE (mois par mois)
# =============================================================================

def fenetres_mensuelles(debut, fin):
    cur = debut.replace(day=1)
    while cur <= fin:
        suivant = (cur.replace(day=28) + dt.timedelta(days=7)).replace(day=1)
        yield cur, min(suivant - dt.timedelta(days=1), fin)
        cur = suivant


def extraire_journalier(cloud, code, stat_type):
    print("\n>> Extraction JOURNALIÈRE...")
    lignes = []
    url = f"/v1.0/devices/{config.DEVICE_ID}/statistics/days"
    for a, b in fenetres_mensuelles(config.DATE_INSTALLATION, dt.date.today()):
        query = {"code": code, "start_day": f"{a:%Y%m%d}", "end_day": f"{b:%Y%m%d}"}
        if stat_type:
            query["stat_type"] = stat_type
        try:
            res = appel(cloud, url, query=query)
        except RuntimeError as e:
            print(f"   {a:%Y-%m} : ERREUR ({e})")
            continue
        jours = (res or {}).get("days", {}) if res else {}
        for jour, val in jours.items():
            lignes.append((jour, val))
        if jours:
            print(f"   {a:%Y-%m} : {len(jours)} jours")
    lignes.sort()
    return lignes


# =============================================================================
# EXTRACTION MENSUELLE (année par année : contrainte Tuya)
# =============================================================================

def extraire_mensuel(cloud, code, stat_type):
    print("\n>> Extraction MENSUELLE...")
    lignes = []
    url = f"/v1.0/devices/{config.DEVICE_ID}/statistics/months"
    for annee in range(config.DATE_INSTALLATION.year, dt.date.today().year + 1):
        query = {"code": code, "start_month": f"{annee}01", "end_month": f"{annee}12"}
        if stat_type:
            query["stat_type"] = stat_type
        try:
            res = appel(cloud, url, query=query)
        except RuntimeError as e:
            print(f"   {annee} : ERREUR ({e})")
            continue
        mois = (res or {}).get("months", {}) if res else {}
        for m, val in mois.items():
            lignes.append((m, val))
        if mois:
            print(f"   {annee} : {len(mois)} mois")
    lignes.sort()
    return lignes


# =============================================================================
# ÉCRITURE CSV
# =============================================================================

def ecrire_csv_jour(lignes):
    with open(config.CSV_JOUR, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["date", "kWh"])
        for jour, val in lignes:
            d = dt.datetime.strptime(jour, "%Y%m%d").date()
            w.writerow([d.isoformat(), val])
    print(f"   -> {len(lignes)} lignes écrites dans {config.CSV_JOUR}")


def ecrire_csv_mois(lignes):
    with open(config.CSV_MOIS, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["mois", "kWh"])
        for m, val in lignes:
            w.writerow([f"{m[:4]}-{m[4:6]}", val])
    print(f"   -> {len(lignes)} lignes écrites dans {config.CSV_MOIS}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print(" Extraction historique consommation Tuya")
    print("=" * 60)

    cloud = connexion()
    code, stat_type = detecter_grandeur(cloud)

    jours = extraire_journalier(cloud, code, stat_type)
    mois = extraire_mensuel(cloud, code, stat_type)

    print("\n>> Écriture des fichiers...")
    if jours:
        ecrire_csv_jour(jours)
    else:
        print("   (aucune donnée journalière — vérifiez le code/la période)")
    if mois:
        ecrire_csv_mois(mois)
    else:
        print("   (aucune donnée mensuelle)")

    print("\n" + "=" * 60)
    if jours:
        total = 0.0
        for _, v in jours:
            try:
                total += float(v)
            except (TypeError, ValueError):
                pass
        d1 = dt.datetime.strptime(jours[0][0], "%Y%m%d").date()
        d2 = dt.datetime.strptime(jours[-1][0], "%Y%m%d").date()
        print(f" Période couverte : {d1} -> {d2}")
        print(f" Total cumulé (somme journalière) : {total:.2f} kWh")
    print(" Terminé.")
    print("=" * 60)


if __name__ == "__main__":
    main()
