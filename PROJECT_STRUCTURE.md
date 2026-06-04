# 📋 Structure Complète du Projet Medical DQV Pipeline

## 🎯 Vue d'ensemble du projet

Ce projet est un **pipeline complet de nettoyage et vérification qualité de données médicales** avec anonymisation RGPD. Il combine :
- 🔄 **Scraping** de données depuis URLs ou fichiers locaux
- 🔐 **Anonymisation** avec k-anonymity et PHI redaction
- ✅ **Vérification Qualité** des données (DQV)
- 🔄 **Transformation** et normalisation
- 📱 **Interface Streamlit** pour interaction utilisateur
- 📊 **Génération de rapports** HTML et JSON
- 💾 **Versioning DVC** des données

**Stack technique** : Python 3.13, Pandas, Scikit-learn, Streamlit, DVC, Great Expectations

---

## 📁 Arborescence Complète du Projet

```
projetDS/
│
├── 🔧 Fichiers de configuration racine
│   ├── config.yaml                  # Configuration globale du pipeline
│   ├── dvc.yaml                     # Définition du pipeline DVC
│   ├── requirements.txt             # Dépendances Python
│   ├── get-pip.py                   # Script d'installation pip
│   │
│   └── 📖 Documentation
│       ├── USAGE_GUIDE.md           # Guide d'utilisation complet
│       ├── RESOLUTION_REPORT.md     # Documentation des problèmes résolus
│       └── PROJECT_STRUCTURE.md     # Ce fichier
│
├── 📱 app/                          # Application Streamlit (Interface utilisateur)
│   ├── app.py                       # Point d'entrée principal Streamlit
│   │                                 # - Navigation entre pages
│   │                                 # - Configuration générale
│   │                                 # - Thème et styles
│   │
│   └── pages/                       # Pages Streamlit multipage
│       ├── 01_collect.py            # Page 1 : Scraping + Anonymisation
│       ├── 02_quality.py            # Page 2 : Vérification Qualité (DQV)
│       └── 03_output.py             # Page 3 : Export et Gestion DVC
│
├── 📊 data/                         # Données brutes et traitées
│   ├── raw/
│   │   ├── medical_raw.csv          # Données brutes téléchargées
│   │   └── test_medical_raw.csv     # Dataset de test
│   │
│   └── processed/
│       ├── medical_v1.0_anonymized.csv    # Après anonymisation
│       ├── medical_v1.0_transformed.csv   # Après transformation (finale)
│       ├── test_anonymized.csv             # Test : anonymisé
│       └── (transformer_pipeline.pkl)     # Scikit-learn pipeline serialisé
│
├── 🔐 src/                          # Code métier (logique réutilisable)
│   ├── scraper.py                   # Scraping de données
│   ├── anonymizer.py                # Anonymisation PHI + k-anonymity
│   ├── dqv.py                       # Data Quality Verification (vérification qualité)
│   ├── pipeline.py                  # Orchestration du pipeline complet
│   ├── transformer.py               # Transformation et normalisation
│   └── dvc_manager.py               # Gestion DVC (versionning)
│
├── 📝 notebooks/                    # Analyses exploratoires (Jupytext)
│   └── 01_eda.py                    # Exploratory Data Analysis
│
├── 📈 reports/                      # Rapports générés
│   ├── dqv_report.html              # Rapport HTML interactif (qualité)
│   ├── dqv_results.json             # Résultats DQV (JSON)
│   ├── anonymization_report.json    # Rapport d'anonymisation
│   ├── infographic_dashboard.html   # Dashboard visuel
│   ├── rapport_technique.md         # Documentation technique
│   ├── test_dqv_report.html         # (Test)
│   ├── test_dqv_results.json        # (Test)
│   └── test_anonymization_report.json # (Test)
│
├── 🧪 tests/                        # Tests unitaires (pytest)
│   ├── test_anonymizer.py           # Tests anonymiseur
│   └── test_dqv.py                  # Tests vérification qualité
│
├── 💾 dvc_storage/                  # Cache interne DVC
│   └── files/md5/                   # Stockage des versions des données
│
├── 🔍 test_*.py (racine)            # Scripts de test globaux
│   ├── test_full_pipeline.py        # Test complet du pipeline
│   └── test_scraper.py              # Test du scraper
│
└── Exécution
    └── streamlit run app/app.py     # Lancer l'application
```

---

## 📄 Description Détaillée de Chaque Fichier/Dossier

### 🔝 **Racine du Projet**

#### `config.yaml` 
**Rôle** : Configuration centralisée de tout le pipeline
```yaml
project:
  name: "medical-dqv-pipeline"
  version: "1.0.0"

scraper:
  url: "https://archive.ics.uci.edu/.../processed.cleveland.data"
  mode: "static"          # ou "dynamic" (Selenium)
  timeout: 30
  max_retries: 3

anonymization:
  k_anonymity: 3          # k minimum pour anonymité
  strategy: "replace"     # replace | hash | drop
  phi_direct:             # Champs toujours supprimés
    - name
    - nom
    - prenom

paths:
  raw_data: "data/raw/medical_raw.csv"
  anonymized_data: "data/processed/medical_v1.0_anonymized.csv"
  transformed_data: "data/processed/medical_v1.0_transformed.csv"
  dqv_report_html: "reports/dqv_report.html"
  dqv_results_json: "reports/dqv_results.json"
```
**Utilisation** : Lue par tous les modules du projet (scraper, anonymizer, dqv, etc.)

---

#### `dvc.yaml`
**Rôle** : Définition du pipeline orchestré par DVC (Data Version Control)
```yaml
stages:
  scrape:
    cmd: python src/scraper.py
    deps: [src/scraper.py, config.yaml]
    outs: [data/raw/medical_raw.csv]
    
  anonymize:
    cmd: python -c "..."
    deps: [src/anonymizer.py, data/raw/medical_raw.csv]
    outs: [data/processed/medical_v1.0_anonymized.csv]
    
  dqv:
    cmd: python -c "..."
    deps: [src/dqv.py, data/processed/medical_v1.0_anonymized.csv]
```
**Utilisation** : `dvc repro` pour rejouer le pipeline complet

---

#### `requirements.txt`
**Rôle** : Toutes les dépendances Python du projet
```
# Data
pandas>=2.2.2
numpy>=2.1.0
scikit-learn>=1.6.0

# Scraping
requests>=2.32.3
beautifulsoup4>=4.12.3
selenium>=4.21.0

# Anonymisation
faker>=25.2.0

# Qualité
great-expectations>=1.0.0
pandera>=0.20.0

# Interface
streamlit>=1.35.0
plotly>=5.22.0

# Versioning
dvc>=3.51.2
```
**Utilisation** : `pip install -r requirements.txt`

---

#### `USAGE_GUIDE.md`
**Rôle** : Guide complet d'utilisation (installation, démarrage, configuration)
- Comment installer l'environnement
- Comment lancer l'application Streamlit
- Comment utiliser les 3 pages de l'interface
- Solutions pour les datasets Kaggle

---

#### `RESOLUTION_REPORT.md`
**Rôle** : Documentation des problèmes identifiés et résolutions

---

#### `test_full_pipeline.py`, `test_scraper.py`
**Rôle** : Scripts de test pour valider le pipeline complet et le scraper

---

### 📱 **Dossier `app/` — Application Streamlit**

#### `app.py` (Point d'entrée)
**Rôle** : Application Streamlit principale
- Configuration Streamlit (titre, icône, layout)
- Navigation multipage (st.navigation)
- Barre latérale avec paramètres globaux
- Gestion des sessions et cache

**Code type** :
```python
import streamlit as st
from pages import collect, quality, output

st.set_page_config(page_title="Medical DQV Pipeline", layout="wide")

# Navigation
page = st.navigation([
    st.Page(collect.py, title="01 - Collect"),
    st.Page(quality.py, title="02 - Quality"),
    st.Page(output.py, title="03 - Output")
])

page.run()
```

---

#### `pages/01_collect.py` — Scraping + Anonymisation
**Rôle** : Interface utilisateur pour l'étape 1

**Fonctionnalités** :
- Sélection de source de données :
  - Dataset prédéfini (Heart Disease, Diabetes, etc.)
  - URL HTTP/HTTPS vers CSV brut
  - URL vers page HTML avec tableau
  - Chemin local vers fichier CSV
- Choix du mode scraping : `static` (HTTP) ou `dynamic` (Selenium)
- Configuration d'anonymisation :
  - Valeur de k-anonymity (k=3, k=5, k=10...)
  - Stratégie : replace (Faker), hash, drop
- Bouton "🚀 Lancer Collecte + Anonymisation"
- Affichage des résultats et du rapport

---

#### `pages/02_quality.py` — Vérification Qualité (DQV)
**Rôle** : Interface pour la vérification qualité des données

**Fonctionnalités** :
- Affichage du rapport DQV en onglets :
  - Vue générale (complétude, duplicatas, etc.)
  - Analyse statistique par colonne
  - Détection d'anomalies
  - Gate check : ✅ ACCEPTÉ ou ❌ REJETÉ
- Visualisations interactives (Plotly)
- Export du rapport HTML

---

#### `pages/03_output.py` — Export et Gestion DVC
**Rôle** : Interface pour télécharger et gérer les données

**Fonctionnalités** :
- Aperçu du dataset final transformé
- Téléchargement du CSV en local
- Gestion DVC :
  - Commit des versions
  - Historique des versions
  - Push/Pull vers stockage distant (optionnel)

---

### 📊 **Dossier `data/` — Données du Pipeline**

#### `data/raw/`
- `medical_raw.csv` : Données brutes téléchargées depuis la source (URL ou fichier)
- `test_medical_raw.csv` : Dataset de test pour validation

**Contenu type** : Colonnes non traitées, valeurs manquantes potentielles, format original

---

#### `data/processed/`
- `medical_v1.0_anonymized.csv` : Après anonymisation (PHI supprimée, k-anonymity appliquée)
- `medical_v1.0_transformed.csv` : Après transformation (colonnes normalisées, encoding, scaling)
- `test_anonymized.csv` : Version anonymisée du dataset de test
- `transformer_pipeline.pkl` : Pipeline scikit-learn sérialisé (pour appliquer transformation à nouvelles données)

**Étapes de transformation** :
1. Scraping → `medical_raw.csv`
2. Anonymisation → `medical_v1.0_anonymized.csv`
3. Transformation (encoding, scaling) → `medical_v1.0_transformed.csv`

---

### 🔐 **Dossier `src/` — Code Métier**

#### `scraper.py` — Téléchargement de Données
**Classe/Fonction** : `MedicalScraper`

**Rôle** :
- Télécharge des données depuis une source
- Supporte plusieurs formats/sources :
  - URLs HTTP/HTTPS vers CSV brut
  - URLs vers pages HTML avec tableaux (BeautifulSoup)
  - Chemins locaux vers fichiers CSV
  - Intégration Kaggle API (optionnel)

**Implémentation type** :
```python
class MedicalScraper:
    def __init__(self, url, mode="static", timeout=30):
        self.url = url
        self.mode = mode  # "static" ou "dynamic"
        
    def scrape(self):
        if self.mode == "static":
            return self._scrape_http()
        else:
            return self._scrape_selenium()
            
    def _scrape_http(self):
        # Télécharge CSV brut ou HTML
        ...
        
    def _scrape_selenium(self):
        # JavaScript rendering avec Selenium
        ...
```

**Dépendances** : `requests`, `beautifulsoup4`, `selenium`, `pandas`

---

#### `anonymizer.py` — Anonymisation PHI + K-Anonymity
**Classe** : `MedicalAnonymizer`

**Rôle** :
- Anonymise les données sensibles (PHI : Protected Health Information)
- Applique k-anonymity pour prévenir ré-identification

**Implémentation type** :
```python
class MedicalAnonymizer:
    def __init__(self, k=3, strategy="replace", phi_direct=None):
        self.k = k  # k-anonymity value
        self.strategy = strategy  # "replace" | "hash" | "drop"
        self.phi_direct = phi_direct or ["name", "prenom", "ssn"]
        
    def run(self, df):
        # 1. Supprime/remplace identifiants directs (PHI)
        df = self._handle_phi(df)
        
        # 2. Applique k-anonymity sur quasi-identifiants
        df = self._apply_k_anonymity(df)
        
        # 3. Génère rapport
        report = self._generate_report(df)
        
        return df, report
```

**Stratégies** :
- **replace** : Remplace PHI par données synthétiques (Faker)
- **hash** : Hash HMAC des identifiants
- **drop** : Supprime simplement les colonnes

**Dépendances** : `pandas`, `faker`, `hashlib`

---

#### `dqv.py` — Data Quality Verification (Vérification Qualité)
**Classe** : `DataQualityVerifier`

**Rôle** :
- Vérifie la qualité des données selon critères définis
- Produit rapport HTML interactif et JSON
- Retourne un "gate" (✅ ACCEPTÉ ou ❌ REJETÉ)

**Vérifications** :
- ✅ Complétude (% de valeurs non-manquantes)
- ✅ Unicité et duplicatas
- ✅ Valeurs aberrantes (outliers) par colonne
- ✅ Formats valides (date, email, etc.)
- ✅ Plages de valeurs (min/max)
- ✅ Distributions statistiques

**Implémentation type** :
```python
class DataQualityVerifier:
    def __init__(self, config):
        self.config = config  # Seuils acceptables
        
    def run(self, df):
        results = {}
        
        # Vérifications
        results['completeness'] = self._check_completeness(df)
        results['duplicates'] = self._check_duplicates(df)
        results['outliers'] = self._check_outliers(df)
        results['formats'] = self._check_formats(df)
        
        # Gate : ✅ si tout OK, ❌ sinon
        gate = all(r['status'] == 'PASS' for r in results.values())
        
        return gate, results
```

**Dépendances** : `great-expectations`, `pandera`, `pandas`, `plotly`

---

#### `pipeline.py` — Orchestration du Pipeline
**Classe** : `MedicalDataPipeline`

**Rôle** :
- Chaîne les étapes du pipeline
- Gère les dépendances entre modules
- Enregistre les logs

**Flux** :
```
Input (URL/fichier)
   ↓
[scraper.py] → medical_raw.csv
   ↓
[anonymizer.py] → medical_v1.0_anonymized.csv + rapport
   ↓
[dqv.py] → medical_v1.0_anonymized.csv (validé) + rapport DQV
   ↓
[transformer.py] → medical_v1.0_transformed.csv + pipeline.pkl
   ↓
Output (CSV + Rapports)
```

**Implémentation type** :
```python
class MedicalDataPipeline:
    def run(self, url, k=3, strategy="replace"):
        # Étape 1
        df = MedicalScraper(url).scrape()
        
        # Étape 2
        df, anon_report = MedicalAnonymizer(k, strategy).run(df)
        
        # Étape 3
        gate, dqv_results = DataQualityVerifier().run(df)
        
        if gate:
            # Étape 4
            df, pipeline = Transformer().fit_transform(df)
            return df, pipeline, anon_report, dqv_results
        else:
            raise QualityGateError("Data failed quality checks")
```

---

#### `transformer.py` — Transformation et Normalisation
**Classe** : `Transformer`

**Rôle** :
- Encode colonnes catégoriques (OneHotEncoder, LabelEncoder)
- Normalise/scale colonnes numériques (StandardScaler, MinMaxScaler)
- Sérialise le pipeline pour appliquer à nouvelles données

**Implémentation type** :
```python
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder

class Transformer:
    def __init__(self):
        self.pipeline = Pipeline([
            ('encoder', OneHotEncoder(sparse_output=False)),
            ('scaler', StandardScaler())
        ])
        
    def fit_transform(self, df):
        df_transformed = self.pipeline.fit_transform(df)
        
        # Sérialisation
        joblib.dump(self.pipeline, 'data/processed/transformer_pipeline.pkl')
        
        return df_transformed, self.pipeline
```

**Dépendances** : `scikit-learn`, `joblib`

---

#### `dvc_manager.py` — Gestion DVC (Versionning)
**Classe** : `DVCManager`

**Rôle** :
- Gère le versioning des données avec DVC
- Enregistre versions, commit, push/pull
- Permet traçabilité complète

**Implémentation type** :
```python
class DVCManager:
    def __init__(self, repo_path="."):
        self.repo = Repo(repo_path)
        
    def commit(self, message):
        os.system(f'dvc commit -m "{message}"')
        
    def push(self):
        os.system('dvc push')
        
    def pull(self):
        os.system('dvc pull')
        
    def get_versions(self):
        # Récupère l'historique des versions
        ...
```

**Dépendances** : `dvc`, `gitpython`

---

### 📝 **Dossier `notebooks/` — Analyses Exploratoires**

#### `01_eda.py` — Exploratory Data Analysis
**Format** : Jupytext (notebook Python exécutable)

**Contenu type** :
- Statistiques descriptives des données
- Visualisations (matplotlib, seaborn, plotly)
- Détection de patterns/anomalies
- Corrélations entre colonnes
- Distribution des variables

**Utilisation** : Exploration interactive avec Jupyter ou JupyterLab

---

### 📈 **Dossier `reports/` — Rapports Générés**

#### `dqv_report.html`
**Généré par** : `dqv.py`
- Rapport interactif avec Plotly
- Onglets par métrique (complétude, duplicatas, outliers, etc.)
- Visualisations statiques et interactives
- Résumé executif avec gate (✅/❌)

---

#### `dqv_results.json`
**Généré par** : `dqv.py`
- Format JSON des résultats DQV
- Détails par colonne
- Métriques exactes (%, counts, etc.)
- Utilisable pour automatisation

**Exemple** :
```json
{
  "timestamp": "2026-06-04T10:30:00",
  "gate": true,
  "metrics": {
    "completeness": 95.5,
    "duplicates_count": 12,
    "outliers": {...}
  }
}
```

---

#### `anonymization_report.json`
**Généré par** : `anonymizer.py`
- Statistiques d'anonymisation
- Nombre de valeurs supprimées/remplacées/hachées
- Vérification de k-anonymity
- PHI redaction summary

---

#### `infographic_dashboard.html`
**Généré par** : Application Streamlit
- Dashboard visuel des résultats
- Métriques clés
- Charts interactifs

---

#### `rapport_technique.md`
**Type** : Documentation technique
- Architecture du projet
- Méthodologie d'anonymisation
- Paramètres utilisés
- Résultats globaux

---

#### `test_*.html`, `test_*.json`
Versions des rapports générés sur le dataset de test

---

### 🧪 **Dossier `tests/` — Tests Unitaires**

#### `test_anonymizer.py`
**Framework** : pytest
**Tests** :
- Test de suppression/remplacement PHI
- Test de k-anonymity
- Test de conservation de format
- Validation des rapports

**Exécution** : `pytest tests/test_anonymizer.py`

---

#### `test_dqv.py`
**Framework** : pytest
**Tests** :
- Test des vérifications de qualité
- Test des seuils de gate
- Test de génération de rapports
- Test des détections d'anomalies

**Exécution** : `pytest tests/test_dqv.py`

---

### 💾 **Dossier `dvc_storage/` — Cache Local DVC**

#### `files/md5/`
**Rôle** : Cache interne de DVC
- Stockage des versions des données
- Hachage MD5 des fichiers
- Permet rejouer du pipeline sans re-télécharger

**Utilisation interne** : Automatique avec `dvc repro`

---

## 🔄 **Flux Complet du Pipeline**

```
┌─────────────────────────────────────────────────────────────────┐
│                    UTILISATEUR                                  │
│            (Interface Streamlit - pages 1-3)                    │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ↓
        ┌─────────────────────────────┐
        │  01_collect.py (Page 1)     │
        │  Saisir données, param      │
        └──────────┬──────────────────┘
                   │
                   ↓
        ┌─────────────────────────────┐
        │  scraper.py                 │
        │  Télécharge données          │
        └──────────┬──────────────────┘
                   │
                   ↓
        ┌─────────────────────────────┐
        │  data/raw/medical_raw.csv   │
        │  (Données brutes)           │
        └──────────┬──────────────────┘
                   │
                   ↓
        ┌─────────────────────────────┐
        │  anonymizer.py              │
        │  Anonymise PHI + k-anon     │
        └──────────┬──────────────────┘
                   │
                   ↓
        ┌─────────────────────────────┐
        │  medical_v1.0_anonymized.csv│
        │  + anonymization_report.json│
        └──────────┬──────────────────┘
                   │
                   ↓
        ┌─────────────────────────────┐
        │  dqv.py                     │
        │  Vérification Qualité       │
        └──────────┬──────────────────┘
                   │
                   ↓
        ┌─────────────────────────────┐
        │  02_quality.py (Page 2)     │
        │  Affiche rapport DQV        │
        │  Gate: ✅ ou ❌             │
        └──────────┬──────────────────┘
                   │
                   ↓ (si ✅)
        ┌─────────────────────────────┐
        │  transformer.py             │
        │  Normalise + Encode         │
        └──────────┬──────────────────┘
                   │
                   ↓
        ┌─────────────────────────────┐
        │  medical_v1.0_transformed.csv
        │  + pipeline.pkl             │
        └──────────┬──────────────────┘
                   │
                   ↓
        ┌─────────────────────────────┐
        │  03_output.py (Page 3)      │
        │  Télécharge + DVC versioning│
        └─────────────────────────────┘
```

---

## ⚙️ **Installation et Démarrage**

### Installation
```bash
# Créer environnement virtuel
python -m venv venv
source venv/Scripts/activate  # Windows

# Installer dépendances
pip install -r requirements.txt

# Initialiser DVC (optionnel)
dvc init
```

### Lancer l'application
```bash
cd c:\projetDS
streamlit run app/app.py
```

### Rejouer le pipeline avec DVC
```bash
dvc repro
```

### Lancer les tests
```bash
pytest tests/
pytest tests/test_anonymizer.py -v
pytest tests/test_dqv.py -v
```

---

## 📊 **Technologies Utilisées**

| Domaine | Technologie | Rôle |
|---------|------------|------|
| **Data** | Pandas, NumPy | Manipulation de données |
| **Scraping** | Requests, BeautifulSoup, Selenium | Téléchargement/parsing |
| **ML** | Scikit-learn, Joblib | Transformation, pipeline |
| **Qualité** | Great-Expectations, Pandera | Vérification qualité |
| **Anonymisation** | Faker | Données synthétiques |
| **Interface** | Streamlit | Application web |
| **Visualisation** | Plotly, Matplotlib, Seaborn | Graphiques/rapports |
| **Versioning** | DVC | Versioning données |
| **Tests** | Pytest | Tests unitaires |
| **Config** | YAML | Configuration centralisée |

---

## 🎯 **Cas d'Usage**

### 1️⃣ **Chercheur en santé**
- Utilise interface Streamlit
- Télécharge dataset Kaggle
- Lance pipeline en 3 clics
- Récupère données anonymisées + rapport qualité

### 2️⃣ **Data Engineer**
- Modifie config.yaml pour paramètres custom
- Lance `dvc repro` pour pipeline complet
- Consulte rapports JSON pour automation
- Gère versions DVC

### 3️⃣ **Data Scientist**
- Explore données dans notebook EDA
- Teste différentes stratégies anonymisation
- Exécute `pytest` pour validation
- Utilise données transformées pour ML

---

## 📚 **Ressources Supplémentaires**

- **[USAGE_GUIDE.md](USAGE_GUIDE.md)** — Guide détaillé d'utilisation
- **[RESOLUTION_REPORT.md](RESOLUTION_REPORT.md)** — Problèmes et solutions
- **[config.yaml](config.yaml)** — Tous les paramètres
- **[dvc.yaml](dvc.yaml)** — Pipeline DVC

---

**Dernière mise à jour** : Juin 2026
**Version** : 1.0.0
**Statut** : Production-ready ✅
