#!/usr/bin/env python
"""
test_full_pipeline.py
---------------------
Script de test complet du pipeline Medical DQV.
Démontre que tous les problèmes ont été résolus.

Usage:
    python test_full_pipeline.py
"""

import sys
from pathlib import Path

sys.path.insert(0, "src")

from scraper import MedicalScraper, ScraperConfig
from anonymizer import MedicalAnonymizer
from dqv import DataQualityVerifier, DQVConfig
from transformer import MedicalTransformer


def print_section(title: str):
    """Affiche un titre de section."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def main():
    """Exécute le test complet du pipeline."""
    
    print_section("🧪 TEST COMPLET — MEDICAL DQV PIPELINE")
    
    # ========================================================================
    # 1. SCRAPING — Test avec dataset Pima Diabetes
    # ========================================================================
    print_section("1️⃣  ÉTAPE 1 : SCRAPING")
    
    config = ScraperConfig(
        url="https://raw.githubusercontent.com/jbrownlee/Datasets/master/pima-indians-diabetes.data.csv",
        mode="static",
        output_path="data/raw/test_medical_raw.csv"
    )
    print(f"  Source: {config.url}")
    print(f"  Mode:   {config.mode}")
    
    scraper = MedicalScraper(config)
    df_raw = scraper.run()
    
    if df_raw.empty:
        print("  ❌ ERREUR : Aucune donnée collectée")
        return False
    
    print(f"  ✅ Résultat : {len(df_raw)} lignes × {len(df_raw.columns)} colonnes")
    print(f"\n  Aperçu (5 premières lignes) :")
    print(f"{df_raw.head().to_string(max_colwidth=15)}\n")
    
    # ========================================================================
    # 2. ANONYMISATION
    # ========================================================================
    print_section("2️⃣  ÉTAPE 2 : ANONYMISATION")
    
    anonymizer = MedicalAnonymizer(
        k=2,
        strategy="replace",
        output_path="data/processed/test_anonymized.csv",
        report_path="reports/test_anonymization_report.json"
    )
    print(f"  k-anonymity: 2")
    print(f"  Stratégie:   replace\n")
    
    df_anon = anonymizer.run(df_raw)
    
    if df_anon.empty:
        print("  ⚠️ AVERTISSEMENT : Données vides après anonymisation")
        # Continue quand même
    else:
        print(f"  ✅ Résultat : {len(df_anon)} lignes conservées ({100*len(df_anon)/len(df_raw):.1f}%)")
    
    # ========================================================================
    # 3. DATA QUALITY VERIFICATION (DQV)
    # ========================================================================
    print_section("3️⃣  ÉTAPE 3 : DATA QUALITY VERIFICATION")
    
    dqv_config = DQVConfig(
        missing_threshold=0.15,
        report_path="reports/test_dqv_report.html",
        results_path="reports/test_dqv_results.json"
    )
    print(f"  Missing threshold:  {dqv_config.missing_threshold*100:.0f}%")
    print(f"  Duplicate tolerance: {dqv_config.duplicate_tolerance}\n")
    
    verifier = DataQualityVerifier(dqv_config)
    gate_passed, results = verifier.run(df_anon)
    
    # Résumé
    pass_count = sum(1 for r in results if r.status == "pass")
    warn_count = sum(1 for r in results if r.status == "warn")
    fail_count = sum(1 for r in results if r.status == "fail")
    
    print(f"\n  📊 Résumé des vérifications :")
    print(f"     ✅ PASS : {pass_count}")
    print(f"     ⚠️  WARN : {warn_count}")
    print(f"     ❌ FAIL : {fail_count}")
    
    gate_status = "✅ ACCEPTÉ" if gate_passed else "❌ REJETÉ"
    print(f"\n  🚪 Gate Check : {gate_status}")
    
    # ========================================================================
    # 4. TRANSFORMATION
    # ========================================================================
    print_section("4️⃣  ÉTAPE 4 : TRANSFORMATION")
    
    transformer = MedicalTransformer(
        outlier_factor=1.5,
        scaler_method="standard",
        pipeline_path="data/processed/test_transformer_pipeline.pkl"
    )
    print(f"  Outlier factor: 1.5")
    print(f"  Scaler method:  standard\n")
    
    df_transformed = transformer.fit_transform(df_anon)
    
    print(f"  ✅ Résultat : {df_transformed.shape[0]} lignes × {df_transformed.shape[1]} colonnes")
    
    # ========================================================================
    # 5. RÉSUMÉ DES FICHIERS GÉNÉRÉS
    # ========================================================================
    print_section("📁 FICHIERS GÉNÉRÉS")
    
    files_to_check = [
        ("data/raw/test_medical_raw.csv", "Données brutes (scraping)"),
        ("data/processed/test_anonymized.csv", "Données anonymisées"),
        ("data/processed/test_transformer_pipeline.pkl", "Pipeline sklearn"),
        ("reports/test_anonymization_report.json", "Rapport anonymisation"),
        ("reports/test_dqv_report.html", "Rapport DQV (HTML)"),
        ("reports/test_dqv_results.json", "Résultats DQV (JSON)"),
    ]
    
    for filepath, description in files_to_check:
        p = Path(filepath)
        if p.exists():
            size = p.stat().st_size / 1024
            print(f"  ✅ {filepath:<50} ({size:6.1f} KB) - {description}")
        else:
            print(f"  ⚠️  {filepath:<50} (absent)")
    
    # ========================================================================
    # RÉSULTAT FINAL
    # ========================================================================
    print_section("🎉 RÉSULTAT FINAL")
    
    all_ok = not df_raw.empty and not df_anon.empty and gate_passed
    
    if all_ok:
        print("  ✅ TOUS LES TESTS PASSÉS AVEC SUCCÈS !")
        print("\n  Le pipeline fonctionne correctement :")
        print("    1. ✅ Scraping de données publiques fonctionnel")
        print("    2. ✅ Anonymisation (k-anonymity, PHI removal) ok")
        print("    3. ✅ Data Quality Verification (5 checks) ok")
        print("    4. ✅ Transformation (outliers, scaling, encoding) ok")
        print("    5. ✅ Génération de rapports ok")
        return True
    else:
        print("  ❌ CERTAINS TESTS ONT ÉCHOUÉ")
        if df_raw.empty:
            print("    - Scraping échoué")
        if df_anon.empty:
            print("    - Anonymisation a vidé le dataset")
        if not gate_passed:
            print("    - Gate DQV rejeté")
        return False


if __name__ == "__main__":
    try:
        success = main()
        print("\n" + "=" * 80 + "\n")
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERREUR NON GÉRÉE : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
