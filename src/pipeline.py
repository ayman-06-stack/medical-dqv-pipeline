"""
pipeline.py
-----------
Orchestrateur principal du pipeline médical.
Enchaîne : scraping → anonymisation → DQV → transformation → versioning DVC.
Point d'entrée CLI avec gestion du gate check.
"""

import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from scraper import MedicalScraper, ScraperConfig
from anonymizer import MedicalAnonymizer
from dqv import DataQualityVerifier, DQVConfig
from transformer import MedicalTransformer
from dvc_manager import DVCManager, DVCError

# ---------------------------------------------------------------------------
# Logging centralisé
# ---------------------------------------------------------------------------

def setup_logging(log_path: str = "reports/pipeline.log") -> None:
    """Configure le logging vers console + fichier."""
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )


logger = logging.getLogger("pipeline")


# ---------------------------------------------------------------------------
# Configuration du pipeline
# ---------------------------------------------------------------------------

@dataclass
class PipelineConfig:
    """Configuration complète du pipeline médical."""

    # Source
    source_url: str = "https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/processed.cleveland.data"
    scraper_mode: str = "static"          # "static" | "dynamic"

    # Chemins
    raw_path: str = "data/raw/medical_raw.csv"
    anonymized_path: str = "data/processed/medical_v1.0_anonymized.csv"
    transformed_path: str = "data/processed/medical_v1.0_transformed.csv"
    pipeline_pkl_path: str = "data/processed/transformer_pipeline.pkl"

    # Anonymisation
    k_anonymity: int = 3
    phi_strategy: str = "replace"         # "replace" | "hash" | "drop"

    # DQV
    missing_threshold: float = 0.15
    outlier_factor: float = 1.5
    scaler_method: str = "standard"

    # DVC
    version_tag: str = field(
        default_factory=lambda: f"v1.0-anonymized-{datetime.now().strftime('%Y%m%d')}"
    )
    dvc_push: bool = False                # False par défaut (remote peut ne pas être configuré)

    # Rapports
    dqv_report_path: str = "reports/dqv_report.html"
    anon_report_path: str = "reports/anonymization_report.json"
    log_path: str = "reports/pipeline.log"


# ---------------------------------------------------------------------------
# Résultat du pipeline
# ---------------------------------------------------------------------------

@dataclass
class PipelineResult:
    success: bool
    steps_completed: list
    gate_passed: Optional[bool] = None
    output_path: Optional[str] = None
    version_tag: Optional[str] = None
    error: Optional[str] = None
    duration_seconds: Optional[float] = None

    def summary(self) -> str:
        status = "✅ SUCCÈS" if self.success else "❌ ÉCHEC"
        lines = [
            "",
            "=" * 55,
            f"  RÉSULTAT DU PIPELINE : {status}",
            "=" * 55,
            f"  Étapes complétées    : {', '.join(self.steps_completed)}",
            f"  Gate DQV             : {'✅ Accepté' if self.gate_passed else '❌ Rejeté'}",
            f"  Dataset final        : {self.output_path or 'N/A'}",
            f"  Version DVC          : {self.version_tag or 'N/A'}",
            f"  Durée                : {self.duration_seconds:.1f}s" if self.duration_seconds else "",
        ]
        if self.error:
            lines.append(f"  Erreur               : {self.error}")
        lines.append("=" * 55)
        return "\n".join(l for l in lines if l is not None)


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

class MedicalPipeline:
    """
    Orchestrateur du pipeline complet de données médicales.

    Étapes :
        1. Scraping         — collecte des données brutes depuis l'URL source
        2. Anonymisation    — suppression PHI + k-anonymity
        3. DQV              — vérification qualité + gate check
        4. Transformation   — encodage, normalisation, feature engineering
        5. Versioning DVC   — commit + tag de la version finale

    Usage :
        config = PipelineConfig(source_url="https://...")
        pipeline = MedicalPipeline(config)
        result = pipeline.run()
    """

    def __init__(self, config: PipelineConfig):
        self.config = config
        self._steps_completed: list = []
        self._df_raw: Optional[pd.DataFrame] = None
        self._df_anonymized: Optional[pd.DataFrame] = None
        self._df_final: Optional[pd.DataFrame] = None

    def run(self) -> PipelineResult:
        """Exécute le pipeline complet."""
        start = datetime.now()
        logger.info("=" * 55)
        logger.info("  DÉMARRAGE DU PIPELINE MÉDICAL")
        logger.info("=" * 55)
        logger.info(f"  Source     : {self.config.source_url}")
        logger.info(f"  Version    : {self.config.version_tag}")
        logger.info("=" * 55)

        try:
            # Étape 1 : Scraping
            self._df_raw = self._step_scraping()

            # Étape 2 : Anonymisation
            self._df_anonymized = self._step_anonymization(self._df_raw)

            # Étape 3 : DQV + Gate Check
            gate_passed, dqv_results = self._step_dqv(self._df_anonymized)
            if not gate_passed:
                logger.error("Gate DQV REJETÉ — arrêt du pipeline")
                return PipelineResult(
                    success=False,
                    steps_completed=self._steps_completed,
                    gate_passed=False,
                    error="Gate DQV échoué : dataset insuffisamment propre",
                    duration_seconds=(datetime.now() - start).total_seconds(),
                )

            # Étape 4 : Transformation
            self._df_final = self._step_transformation(self._df_anonymized)

            # Étape 5 : Versioning DVC
            version_tag = self._step_dvc_versioning()

            duration = (datetime.now() - start).total_seconds()
            result = PipelineResult(
                success=True,
                steps_completed=self._steps_completed,
                gate_passed=gate_passed,
                output_path=self.config.transformed_path,
                version_tag=version_tag,
            )
            try:
                print(result.summary())
            except UnicodeEncodeError:
                encoded = result.summary().encode(sys.stdout.encoding or 'ascii', errors='replace')
                print(encoded.decode(sys.stdout.encoding or 'ascii'))
            return result

        except Exception as e:
            logger.exception(f"Erreur critique dans le pipeline : {e}")
            return PipelineResult(
                success=False,
                steps_completed=self._steps_completed,
                error=str(e),
                duration_seconds=(datetime.now() - start).total_seconds(),
            )

    # -----------------------------------------------------------------------
    # Étapes individuelles
    # -----------------------------------------------------------------------

    def _step_scraping(self) -> pd.DataFrame:
        logger.info("\n[ÉTAPE 1/5] Scraping des données")
        config = ScraperConfig(
            url=self.config.source_url,
            output_path=self.config.raw_path,
            mode=self.config.scraper_mode,
        )
        scraper = MedicalScraper(config)
        df = scraper.run()

        if df.empty:
            raise ValueError("Scraping échoué : aucune donnée collectée")

        logger.info(f"Scraping OK — {len(df)} lignes × {len(df.columns)} colonnes")
        self._steps_completed.append("scraping")
        return df

    def _step_anonymization(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("\n[ÉTAPE 2/5] Anonymisation PHI + k-anonymity")
        anonymizer = MedicalAnonymizer(
            k=self.config.k_anonymity,
            strategy=self.config.phi_strategy,
            output_path=self.config.anonymized_path,
            report_path=self.config.anon_report_path,
        )
        df_anon = anonymizer.run(df)
        logger.info(f"Anonymisation OK — {len(df_anon)} lignes conservées")
        self._steps_completed.append("anonymisation")
        return df_anon

    def _step_dqv(self, df: pd.DataFrame) -> tuple:
        logger.info("\n[ÉTAPE 3/5] Vérification qualité des données (DQV)")
        dqv_config = DQVConfig(
            missing_threshold=self.config.missing_threshold,
            report_path=self.config.dqv_report_path,
        )
        verifier = DataQualityVerifier(dqv_config)
        gate_passed, results = verifier.run(df)
        self._steps_completed.append("dqv")
        return gate_passed, results

    def _step_transformation(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("\n[ÉTAPE 4/5] Transformation des données")
        transformer = MedicalTransformer(
            outlier_factor=self.config.outlier_factor,
            scaler_method=self.config.scaler_method,
            pipeline_path=self.config.pipeline_pkl_path,
        )
        df_transformed = transformer.fit_transform(df)

        # Sauvegarde du dataset transformé
        output = Path(self.config.transformed_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        df_transformed.to_csv(output, index=False)
        logger.info(f"Transformation OK — dataset sauvegardé → {output}")

        self._steps_completed.append("transformation")
        return df_transformed

    def _step_dvc_versioning(self) -> str:
        logger.info("\n[ÉTAPE 5/5] Versioning DVC")
        try:
            dvc = DVCManager(repo_path=".")
            if not dvc.is_initialized():
                logger.warning("DVC non initialisé — skip versioning")
                self._steps_completed.append("dvc_skipped")
                return self.config.version_tag

            dvc.version_dataset(
                dataset_path=self.config.anonymized_path,
                version_tag=self.config.version_tag,
                push=self.config.dvc_push,
            )
            logger.info(f"Versioning DVC OK — tag : {self.config.version_tag}")
            self._steps_completed.append("dvc_versioning")
            return self.config.version_tag

        except (DVCError, Exception) as e:
            logger.warning(f"Versioning DVC ignoré : {e}")
            self._steps_completed.append("dvc_skipped")
            return self.config.version_tag


# ---------------------------------------------------------------------------
# CLI avec Click
# ---------------------------------------------------------------------------

def main():
    """Point d'entrée CLI du pipeline."""
    try:
        import click

        @click.command()
        @click.option("--url", default=None, help="URL source des données médicales")
        @click.option("--mode", default="static", type=click.Choice(["static", "dynamic"]))
        @click.option("--k", default=3, help="Valeur k pour k-anonymity")
        @click.option("--version", default=None, help="Tag de version DVC (ex: v1.0-anonymized)")
        @click.option("--push/--no-push", default=False, help="Pousser vers remote DVC")
        @click.option("--missing-threshold", default=0.15, help="Seuil valeurs manquantes DQV")
        def cli(url, mode, k, version, push, missing_threshold):
            """Pipeline de nettoyage et versioning de données médicales."""
            setup_logging()
            config = PipelineConfig(
                source_url=url or PipelineConfig.source_url,
                scraper_mode=mode,
                k_anonymity=k,
                version_tag=version or f"v1.0-anonymized-{datetime.now().strftime('%Y%m%d')}",
                dvc_push=push,
                missing_threshold=missing_threshold,
            )
            pipeline = MedicalPipeline(config)
            result = pipeline.run()
            sys.exit(0 if result.success else 1)

        cli()

    except ImportError:
        # Fallback sans Click
        setup_logging()
        logger.info("Click non installé — utilisation de la configuration par défaut")
        config = PipelineConfig()
        pipeline = MedicalPipeline(config)
        result = pipeline.run()
        sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()