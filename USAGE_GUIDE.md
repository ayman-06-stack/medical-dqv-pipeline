# 📖 Guide d'Utilisation — Medical DQV Pipeline

## ⚠️ **IMPORTANT : Kaggle Datasets**

Les URLs Kaggle directes (**`kaggle.com/datasets/...`**) **NE SONT PAS supportées** car elles demandent une authentification.

### ✅ Solutions pour utiliser les datasets Kaggle

#### **Option 1 : Télécharger le CSV manuellement** (Recommandé)
```bash
# 1. Aller sur kaggle.com et télécharger le dataset
# 2. Extraire le fichier CSV
# 3. Dans l'application, utiliser "📁 Fichier CSV local…"
# 4. Entrer le chemin : C:/path/to/healthcare-dataset.csv
```

#### **Option 2 : Utiliser Kaggle CLI**
```bash
# Installer Kaggle CLI
pip install kaggle

# Configurer les credentials (kaggle.json)
# Voir : https://github.com/Kaggle/kaggle-api#api-credentials

# Télécharger le dataset
kaggle datasets download -d prasad22/healthcare-dataset

# Extraire
unzip healthcare-dataset.zip

# Utiliser le chemin local dans l'app
```

#### **Option 3 : Utiliser un dataset UCI public** (Aucune setup)
L'application propose déjà plusieurs datasets publics :
- ✅ Heart Disease (UCI)
- ✅ Diabetes (Pima Indians)
- ✅ Breast Cancer (UCI)
- ✅ Healthcare Data (GitHub)

---

## 🚀 **Démarrage Rapide**

### 1️⃣ Installation
```bash
# Créer un environnement virtuel
python -m venv venv
source venv/Scripts/activate  # Windows
# ou
source venv/bin/activate  # Linux/Mac

# Installer les dépendances
pip install -r requirements.txt

# Installer/activer DVC (optionnel)
dvc init
```

### 2️⃣ Lancer l'Application
```bash
# Depuis le répertoire racine
streamlit run app/app.py
```

### 3️⃣ Utiliser l'Application

#### **Étape 1 : Collecte & Anonymisation** (📁 page)
1. Sélectionner un dataset prédéfini OU entrer une URL/chemin local
2. Choisir le mode scraping (static/dynamic)
3. Configurer k-anonymity et stratégie d'anonymisation
4. Cliquer "🚀 Lancer Collecte + Anonymisation"

**Sources acceptées :**
- URLs HTTP/HTTPS vers CSV brut
- URLs HTTP vers pages HTML avec tableaux
- Chemins locaux vers fichiers CSV

#### **Étape 2 : Vérification Qualité** (✅ page)
- Voir les résultats des vérifications qualité
- Gate check : ACCEPTÉ ✅ ou REJETÉ ❌

#### **Étape 3 : Output & Export** (📦 page)
- Aperçu du dataset transformé
- Télécharger le CSV final
- Gestion des versions DVC

---

## 🔧 **Configuration**

Tous les paramètres sont dans `config.yaml` :

```yaml
scraper:
  url: "..."           # URL source ou chemin local
  mode: "static"       # static ou dynamic
  timeout: 30          # délai HTTP
  
anonymization:
  k_anonymity: 3       # Plus élevé = plus de suppression
  strategy: "replace"  # replace | hash | drop

dqv:
  missing_threshold: 0.15  # Alerte si > 15% manquant
  duplicate_tolerance: 0   # Max doublons tolérés
```

---

## 📊 **Datasets Recommandés**

### ✅ UCI Heart Disease
```
https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/processed.cleveland.data
```
- 303 patients
- 14 colonnes (âge, sexe, tension, etc.)
- Pas d'authentification requise

### ✅ Pima Indians Diabetes
```
https://raw.githubusercontent.com/jbrownlee/Datasets/master/pima-indians-diabetes.data.csv
```
- 768 patients
- 9 colonnes
- Format CSV direct

### ✅ GitHub Healthcare Dataset
```
https://raw.githubusercontent.com/stedy/Healthcare-Data/main/healthcare_data.csv
```
- Données de santé complètes
- Format CSV structuré

---

## ❌ **Erreurs Courantes**

### "❌ URL Kaggle non supportée"
→ **Solution** : Télécharger manuellement depuis Kaggle ou utiliser Kaggle CLI

### "Aucune donnée collectée"
→ **Vérifier** :
- L'URL est valide et accessible
- Le fichier local existe
- La page contient des données (HTML/CSV)
- Le timeout n'a pas expiré

### "k-anonymity : dataset vide après suppression"
→ **Solution** : Réduire `k_anonymity` dans config.yaml (ex: k=2 au lieu de k=3)

### "Erreur Selenium : driver not found"
→ **Solution** : `pip install webdriver-manager` ou télécharger ChromeDriver

---

## 🧪 **Tests**

```bash
# Lancer tous les tests
pytest tests/ -v

# Tests spécifiques
pytest tests/test_anonymizer.py -v
pytest tests/test_dqv.py -v
```

---

## 📋 **Structures des Données**

### Input (Brutes)
```
data/raw/medical_raw.csv
├─ colonnes : age, gender, diagnosis, etc.
└─ peut contenir PHI (identifiants directs)
```

### Output (Anonymisées + Transformées)
```
data/processed/medical_v1.0_anonymized.csv
├─ PHI supprimé/remplacé
├─ k-anonymity appliquée
└─ prêt pour analyse

data/processed/medical_v1.0_transformed.csv
├─ Valeurs imputées
├─ Dates formatées
├─ Outliers traités
├─ Catégories encodées
└─ Features normalisées
```

### Rapports
```
reports/
├─ dqv_report.html        ← Rapport qualité (navigateur)
├─ dqv_results.json       ← Résultats en JSON
├─ anonymization_report.json
└─ pipeline.log
```

---

## 🔐 **Confidentialité & Sécurité**

- ✅ Identification automatique des colonnes PHI
- ✅ Suppression/remplacement des identifiants directs
- ✅ k-anonymity pour quasi-identifiants
- ✅ Logs d'audit avec HMAC
- ⚠️ Données transformées locales (non uploadées)

---

## 📚 **Ressources**

- [k-anonymity Expliquée](https://en.wikipedia.org/wiki/K-anonymity)
- [UCI Machine Learning Repository](https://archive.ics.uci.edu/datasets)
- [Kaggle Datasets](https://kaggle.com/datasets)
- [Great Expectations Documentation](https://greatexpectations.io)
- [DVC Documentation](https://dvc.org/doc)

---

**Besoin d'aide ?** Consultez les logs dans `reports/pipeline.log` 📜
