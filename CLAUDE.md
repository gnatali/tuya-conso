# CLAUDE.md — Contexte projet : extraction historique conso Tuya

Ce fichier est lu automatiquement par Claude Code au démarrage. Il contient tout
le nécessaire pour reprendre le projet sans reconstruire le raisonnement.

## Objectif

Récupérer l'**historique de consommation électrique** d'un compteur triphasé
Tuya **PC321-W-TY** (fabricant OWON/EARU), installé depuis ~3 ans et connecté au
cloud Tuya. Contrainte forte : **ne rien modifier sur l'installation existante**.

Finalité : alimenter un simulateur Excel HC/HP (heures creuses / heures pleines)
avec des données de conso journalières réelles.

## Décision technique clé (à ne pas remettre en cause sans raison)

L'historique long terme est récupérable via le **service Statistiques** du cloud
Tuya, PAS via les logs bruts.

- **Logs bruts d'appareil** (`/v1.0/devices/{id}/logs`) : conservés **7 jours**
  seulement en gratuit. La rétention longue (1–36 mois) est un service payant
  qui n'archive que **vers l'avant** à partir de la souscription → inutile ici,
  car jamais souscrit sur les 3 ans passés. NE PAS partir sur cette piste pour
  l'historique.
- **Service Statistiques** (`/v1.0/devices/{id}/statistics/...`) : données
  **agrégées** par jour/semaine/mois, **conservées sur le long terme**. C'est la
  source qui alimente la courbe de l'app Smart Life. **C'est notre source.**

Confirmé côté utilisateur : l'app Smart Life affiche bien tout l'historique
journalier → le service statistique est actif pour ce produit.

## Endpoints Tuya utilisés

Base EU : `https://openapi.tuyaeu.com` (data center Central Europe).

- `GET /v1.0/devices/{id}/all-statistic-type` → liste des grandeurs (codes)
  disponibles (⚠️ PAS `/statistics` seul : ce chemin n'existe pas côté Tuya et
  renvoie l'erreur 1108 « uri path invalid » — confirmé par test direct le
  2026-07-01).
- `GET /v1.0/devices/{id}/statistics/days?code=X&start_day=YYYYMMDD&end_day=YYYYMMDD`
- `GET /v1.0/devices/{id}/statistics/months?code=X&start_month=YYYYMM&end_month=YYYYMM`
  - **Contrainte** : mois début et fin dans la MÊME année → boucler année/année.
- `GET /v1.0/devices/{id}/statistics/total?code=X` → cumul global (une valeur)

Code énergie : très probablement `add_ele`. Détection auto implémentée via
`/statistics` (priorité add_ele > electricity > *ele*/*energy*).

## Architecture

```
tuya-conso/
├── CLAUDE.md                  # ce fichier
├── README.md                  # doc utilisateur
├── requirements.txt           # tinytuya, python-dotenv
├── setup.sh                   # crée venv .venv, installe, génère .env
├── .env.example               # modèle config (secrets hors code)
├── .gitignore                 # exclut .env, .venv, *.csv
├── config.py                  # charge/valide la config depuis .env
└── extraction_conso_tuya.py   # script principal
```

### Rôle des modules

- **config.py** : lit `.env` via python-dotenv, valide les variables requises,
  sort proprement avec message d'aide si manquant. Expose API_REGION, API_KEY,
  API_SECRET, DEVICE_ID, DATE_INSTALLATION (date), CODE_ENERGIE (str|None),
  CSV_JOUR, CSV_MOIS.
  Si `tinytuya.json` existe à la racine (généré par
  `python -m tinytuya wizard`), il est utilisé **en priorité sur `.env`** pour
  API_REGION/API_KEY/API_SECRET/DEVICE_ID. `.env` reste requis pour
  INSTALL_DATE et CODE_ENERGIE (absents du fichier wizard).
- **extraction_conso_tuya.py** : connexion Cloud, détection code énergie,
  extraction journalière (boucle mois/mois), mensuelle (boucle année/année),
  écriture CSV (séparateur `;`), récap final.

## Choix d'implémentation

- **TinyTuya** (lib Python) gère la signature HMAC-SHA256 et le renouvellement
  du token (expire toutes les 2h). Méthode clé : `Cloud.cloudrequest(url)` —
  vérifiée présente en v1.19. Ne PAS recoder la signature à la main.
- Secrets externalisés dans `.env` (souveraineté / versionnable sous Git).
- CSV en séparateur `;` pour import Excel en locale FR.

## Codes d'erreur Tuya gérés (fonction `appel`)

| Code     | Sens / action |
|----------|---------------|
| 1004     | Signature KO : vérifier ACCESS_ID/SECRET + région |
| 1106     | Permission : lier compte app au projet (onglet Devices) |
| 1010     | Token invalide/expiré (TinyTuya renouvelle seul) |
| 28841105 | API non autorisée : souscrire IoT Core + Smart Home Basic |
| 28841002 | Abonnement IoT Core expiré : prolonger l'essai |
| 2007     | Stats non activées pour le produit (ticket PID/DP) |
| 1108     | URI invalide : mauvais chemin d'endpoint (ex. `/statistics` seul au lieu de `/all-statistic-type`) |
| 28841101 | API non souscrite : le service Statistiques doit être souscrit séparément dans Cloud > Cloud Services (Tuya IoT Platform), en plus de IoT Core / Smart Home Basic |

## Prérequis côté Tuya IoT Platform

Projet cloud (Smart Home), data center **Central Europe**, compte Smart Life
lié (onglet Devices > Link App Account, QR code), APIs **IoT Core** +
**Smart Home Basic Service** souscrites/autorisées. Access ID/Secret dans
Overview. Device ID via wizard TinyTuya (`python -m tinytuya wizard`) ou app.

⚠️ **CORRECTIF (2026-07-01)** : contrairement à ce qu'on pensait au départ,
l'API Statistiques n'est **PAS en libre-service** dans Cloud > Cloud Services
(l'utilisateur a cherché « Advanced Device Services »/« Device Statistics » et
ne les a pas trouvés — normal, ils ne sont pas proposés en auto-souscription).

L'activation nécessite un **ticket de support Tuya**, car l'API doit être
débloquée manuellement par les équipes Tuya pour le PID (Product ID) et les DP
(Data Point) concernés. C'est cohérent avec le code d'erreur 2007 déjà repéré
plus bas — 28841101 est en fait la même famille de blocage, rencontrée plus
tôt dans le flux (à `/all-statistic-type`, avant même d'atteindre 2007 sur
`/statistics/days`).

Procédure :
1. Sur https://developer.tuya.com, **Tech Support** (coin haut droit) →
   Service Center (https://service.console.tuya.com/) → soumettre un
   **General Ticket** (pas de Quick Ticket dédié aux stats a priori).
2. Dans le ticket, indiquer explicitement :
   - **Product ID (PID)** du compteur PC321 : `9rjjf6rdkca9woju`
   - **Data Point (DP) à activer pour les statistiques** : DP `131`
     (code `EnergyConsumed`, énergie cumulée totale). Si besoin de la
     ventilation par phase, ajouter aussi DP `106`/`116`/`126`
     (`EnergyConsumedA`/`B`/`C`).
   - Demander l'activation du **service Statistiques** (`/statistics/days`,
     `/statistics/months`, `/statistics/total`, `/all-statistic-type`) pour ce
     PID/ces DP.
3. Une fois Tuya confirme l'activation côté produit, relancer
   `python extraction_conso_tuya.py`.

**RÉSOLU (2026-07-02)** : le support Tuya a répondu que 28841101 se corrige
en souscrivant le service à cette URL :
https://www.tuya.com/vas/commodity/INTERNAL_TEST_V2 (pas de ticket PID/DP
nécessaire dans ce cas précis — la réponse ci-dessus documente la piste
initialement recommandée par Tuya, gardée au cas où elle redevienne
pertinente pour un autre produit/compte).

Après souscription, deux bugs supplémentaires sont apparus et ont été
corrigés dans `extraction_conso_tuya.py` :

1. **Paramètres de requête non triés → `1004 sign invalid`**. Le script
   concaténait `code`, `start_day`, `end_day` à la main dans l'URL. Le nouvel
   algorithme de signature Tuya exige que les paramètres soient triés par
   ordre alphabétique de clé pour le calcul de signature (`end_day` <
   `start_day` alphabétiquement ≠ notre ordre) → signature invalide.
   Confirmé par test direct : même requête avec les params réordonnés
   alphabétiquement, ou passés via le dict `query=` de TinyTuya (qui trie
   automatiquement), fonctionne. **Fix** : toujours passer les paramètres via
   `query=` (dict), jamais concaténés dans l'URL.
2. **`stat_type` manquant → données silencieusement à zéro**. `/all-statistic-type`
   renvoie pour chaque code un `stat_type` (ex. `"minux"` pour `EnergyConsumed`
   sur le PC321). Ce paramètre est obligatoire dans `/statistics/days` et
   `/statistics/months` : sans lui, Tuya répond `success: true` mais avec des
   valeurs à `"0.00"` pour toutes les dates — **aucune erreur**, juste des
   données fausses. **Fix** : `detecter_grandeur()` retourne `(code,
   stat_type)` et le repasse à chaque appel days/months.

Après ces deux fix, l'extraction fonctionne : 1279 jours extraits, données
réelles à partir du **2023-12-08** (date d'ajout de l'appareil au compte
cloud Tuya — les jours antérieurs renvoient 0.00, pas d'historique avant
cette date malgré ~3 ans d'installation physique), total 8779.03 kWh sur la
période.

## Démarrage rapide

```bash
bash setup.sh
nano .env                      # ACCESS_ID, ACCESS_SECRET, DEVICE_ID, INSTALL_DATE
source .venv/bin/activate
python extraction_conso_tuya.py
```

Premier run : laisser `CODE_ENERGIE` vide → le script affiche la liste des codes.
Vérifier qu'un mois récent recoupe l'app avant de se fier aux 3 ans.

## Points en suspens / prochaines étapes

1. ~~Confirmer le code énergie réel du PC321~~ **FAIT (2026-07-02)** :
   `EnergyConsumed` (total 3 phases, DP 131), `stat_type=minux`. Codes par
   phase disponibles si besoin : `EnergyConsumedA`/`B`/`C` (DP 106/116/126).
2. **Ventilation HC/HP** : le journalier statistique ne distingue PAS les
   tranches horaires. Deux options à discuter :
   - Si un profil horaire fin est requis → il n'existe pas dans l'historique ;
     il faudrait le construire à partir de maintenant (polling local LAN via
     TinyTuya `Device`, intervalle 5–10 s, cf. historique de conversation).
   - Sinon, appliquer une clé de répartition HC/HP au journalier (approximation).
3. **Intégration simulateur Excel** : le CSV `date;kWh` s'importe directement.
   Prévoir éventuellement une colonne HC/HP si étape 2 tranchée.
4. ~~Vérifier rétention réelle des stats journalières~~ **FAIT (2026-07-02)** :
   les données réelles démarrent le 2023-12-08 (date d'ajout de l'appareil au
   compte cloud Tuya), pas avant malgré l'installation physique ~3 ans plus
   tôt. Rien avant cette date côté Tuya, quelle que soit la méthode.

## Contexte utilisateur (rappel)

- Environnement : Debian/WSL2, Python 3.12, préférence LAN local / souveraineté
  des données (éviter dépendance cloud quand possible).
- Alternative 100 % locale déjà évoquée : polling direct du compteur via
  TinyTuya `Device` (nécessite local_key), sans passer par le cloud — pertinent
  pour le futur, mais inopérant pour récupérer l'historique passé.
