# 🏥 Medical Data Quality Validation Pipeline

Pipeline de validation et de qualité pour les données du secteur médical.

## 📋 Description

Un pipeline robuste et scalable pour traiter, valider et assurer la qualité des données médicales. Conçu pour respecter les normes HIPAA et les standards de l'industrie healthcare.

## 🎯 Objectifs

- ✅ Validation automatisée des données
- ✅ Détection des anomalies
- ✅ Conformité réglementaire
- ✅ Génération de rapports qualité

## 🛠️ Technologies

- **Python 3.x**
- **Pandas**: Manipulation de données
- **Great Expectations**: Validation de données
- **Apache Spark** (optionnel): Big data processing
- **PostgreSQL**: Stockage

## 📊 Fonctionnalités

- ✅ Nettoyage des données
- ✅ Validation des formats
- ✅ Détection de valeurs manquantes
- ✅ Anonymisation HIPAA
- ✅ Rapports détaillés

## 🚀 Installation

```bash
# Clone le repo
git clone https://github.com/ayman-06-stack/medical-dqv-pipeline.git
cd medical-dqv-pipeline

# Créer un environnement virtuel
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate sur Windows

# Installer les dépendances
pip install -r requirements.txt
```

## 📈 Utilisation

```bash
# Lancer le pipeline
python run_pipeline.py --input data/raw_data.csv --output data/validated_data.csv

# Générer un rapport qualité
python generate_report.py --data data/validated_data.csv
```

## 📁 Structure

```
.
├── data/
│   ├── raw/           # Données brutes
│   ├── processed/     # Données nettoyées
│   └── reports/       # Rapports qualité
├── src/
│   ├── validator.py   # Validation
│   ├── cleaner.py     # Nettoyage
│   └── pipeline.py    # Pipeline principal
├── tests/             # Tests unitaires
├── requirements.txt
└── README.md
```

## ✅ Standards respectés

- HIPAA Compliance
- HL7 Standards
- DICOM Standards
- Data Protection Regulation

## 🤝 Contribution

Les contributions sont les bienvenues!

## 📝 Licence

MIT License

## 👤 Auteur

**Ayman Guendouz**
- GitHub: [@ayman-06-stack](https://github.com/ayman-06-stack)
- Email: aymanguendouz07@gmail.com
- LinkedIn: [Ayman Guendouz](https://www.linkedin.com/in/ayman-guendouz)
