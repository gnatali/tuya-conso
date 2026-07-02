# Extraction historique consommation Tuya (PC321-W-TY)

Récupère l'historique de consommation électrique d'un compteur Tuya depuis le
**service Statistiques** du cloud Tuya (jour / mois), sans rien modifier sur
l'installation. C'est la même source de données que la courbe affichée dans
l'app Smart Life — donc conservée sur le long terme, contrairement aux logs
bruts limités à 7 jours.

## Prérequis

- Python 3.10+ (testé sous Debian / WSL2)
- Un projet cloud sur la **Tuya IoT Platform** avec le compte Smart Life lié
  (APIs *IoT Core* et *Smart Home Basic Service* autorisées)
- Les identifiants du projet : `Access ID`, `Access Secret`, et le `Device ID`
  du compteur

## Installation

```bash
bash setup.sh
```

Le script crée le venv `.venv`, installe les dépendances et génère un `.env`
à partir du modèle. Éditez ensuite `.env` avec vos identifiants :

```bash
nano .env
```

Installation manuelle équivalente :

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Alternative : générer la config via le wizard TinyTuya

```bash
python3 -m tinytuya wizard
```

Cette commande produit un fichier `tinytuya.json` (région, Access ID/Secret,
Device ID). **S'il est présent à la racine du projet, il est utilisé en
priorité sur `.env`** pour la connexion (région/clés/device) — `.env` reste
nécessaire pour `INSTALL_DATE` et éventuellement `CODE_ENERGIE`. Ce fichier
n'est pas versionné (voir `.gitignore`).

## Utilisation

```bash
source .venv/bin/activate
python extraction_conso_tuya.py
```

Au premier lancement, laissez `CODE_ENERGIE` vide dans `.env` : le script
détecte automatiquement le code d'énergie via l'endpoint `/statistics` et
affiche la liste des grandeurs disponibles.

### Sorties

- `historique_conso_journalier.csv` — colonnes `date; kWh`
- `historique_conso_mensuel.csv` — colonnes `mois; kWh`

Séparateur `;` pour un import direct dans Excel (locale française).

## Conseils

- **Premier run** : vérifiez que la liste de codes s'affiche et qu'un mois
  récent remonte des valeurs cohérentes avec l'app, avant de vous fier aux
  données complètes.
- **Erreur de permission alors que l'app affiche la courbe** : le projet cloud
  n'a probablement pas souscrit au service *IoT Core*
  (Cloud > Cloud Services, gratuit en période d'essai).
- Le fichier `.env` contient vos secrets et n'est pas versionné (`.gitignore`).

## Structure

```
tuya-conso/
├── README.md
├── requirements.txt
├── setup.sh
├── .env.example
├── .gitignore
├── config.py                  # chargement de la config depuis .env
└── extraction_conso_tuya.py   # script principal
```
