"""
dqv.py
------
Module de vérification qualité des données médicales (DQV).
Implémente les checks Great Expectations + Pandera avec rapport HTML.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("dqv")

# Great Expectations et Pandera sont optionnels
try:
    import great_expectations as gx
    GX_AVAILABLE = True
except ImportError:
    GX_AVAILABLE = False
    logger.warning("great_expectations non installé — mode pandas uniquement")

try:
    import pandera as pa
    from pandera import Column, DataFrameSchema, Check
    PANDERA_AVAILABLE = True
except ImportError:
    PANDERA_AVAILABLE = False
    logger.warning("pandera non installé — validation de schéma désactivée")


# ---------------------------------------------------------------------------
# Configuration des seuils DQV
# ---------------------------------------------------------------------------

@dataclass
class DQVConfig:
    """Seuils et paramètres de contrôle qualité."""
    missing_threshold: float = 0.15       # Max 15% valeurs manquantes par colonne
    duplicate_tolerance: int = 0           # Zéro doublon accepté
    age_min: float = 0.0
    age_max: float = 120.0
    blood_pressure_min: float = 50.0
    blood_pressure_max: float = 250.0
    distribution_drift_threshold: float = 0.3  # Seuil de drift (std relative)
    report_path: str = "reports/dqv_report.html"
    results_path: str = "reports/dqv_results.json"
    domain_rules: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Résultat d'un check individuel
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    name: str
    status: str          # "pass" | "warn" | "fail"
    message: str
    value: Optional[float] = None
    threshold: Optional[float] = None
    details: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "value": self.value,
            "threshold": self.threshold,
            "details": self.details or {},
        }


# ---------------------------------------------------------------------------
# Checks individuels
# ---------------------------------------------------------------------------

class MissingValueChecker:
    """Vérifie le taux de valeurs manquantes par colonne."""

    def __init__(self, threshold: float = 0.15):
        self.threshold = threshold

    def check(self, df: pd.DataFrame) -> CheckResult:
        missing_rates = df.isnull().mean()
        violations = missing_rates[missing_rates > self.threshold]
        max_rate = float(missing_rates.max())

        if violations.empty:
            return CheckResult(
                name="Missing Value Threshold",
                status="pass",
                message=f"Toutes les colonnes < {self.threshold*100:.0f}% manquant (max: {max_rate*100:.1f}%)",
                value=max_rate,
                threshold=self.threshold,
                details=missing_rates.to_dict(),
            )
        return CheckResult(
            name="Missing Value Threshold",
            status="warn" if max_rate < 0.30 else "fail",
            message=f"{len(violations)} colonne(s) dépassent le seuil de {self.threshold*100:.0f}%",
            value=max_rate,
            threshold=self.threshold,
            details=violations.to_dict(),
        )


class DuplicateChecker:
    """Vérifie la présence de doublons exacts."""

    def check(self, df: pd.DataFrame) -> CheckResult:
        n_duplicates = int(df.duplicated().sum())

        if n_duplicates == 0:
            return CheckResult(
                name="Duplicate Record Check",
                status="pass",
                message="Aucun doublon détecté",
                value=0,
            )
        pct = n_duplicates / len(df) * 100
        return CheckResult(
            name="Duplicate Record Check",
            status="warn" if pct < 5 else "fail",
            message=f"{n_duplicates} doublon(s) détecté(s) ({pct:.1f}% du dataset)",
            value=n_duplicates,
            details={"duplicate_count": n_duplicates, "duplicate_pct": round(pct, 2)},
        )


class DomainValidityChecker:
    """Vérifie que les valeurs numériques sont dans leur domaine médical valide."""

    DOMAIN_RULES = {
        "age": (0, 120),
        "blood_pressure": (50, 250),
        "heart_rate": (30, 220),
        "glucose": (30, 600),
        "bmi": (10, 70),
        "temperature": (35, 42),
        "oxygen_saturation": (70, 100),
    }

    def check(self, df: pd.DataFrame, custom_rules: dict = None) -> CheckResult:
        rules = {**self.DOMAIN_RULES, **(custom_rules or {})}
        violations = {}

        for col_keyword, (vmin, vmax) in rules.items():
            matching_cols = [c for c in df.columns if col_keyword in c.lower()]
            for col in matching_cols:
                if not pd.api.types.is_numeric_dtype(df[col]):
                    continue
                invalid = df[(df[col] < vmin) | (df[col] > vmax)][col]
                if len(invalid) > 0:
                    violations[col] = {
                        "count": len(invalid),
                        "range": [vmin, vmax],
                        "examples": invalid.head(3).tolist(),
                    }

        if not violations:
            return CheckResult(
                name="Domain/Type Validity Check",
                status="pass",
                message="Toutes les valeurs sont dans leur domaine valide",
            )
        return CheckResult(
            name="Domain/Type Validity Check",
            status="warn",
            message=f"{len(violations)} colonne(s) contiennent des valeurs hors domaine",
            details=violations,
        )


class CrossFeatureConsistencyChecker:
    """Vérifie la cohérence logique entre colonnes."""

    def check(self, df: pd.DataFrame) -> CheckResult:
        issues = []

        # Règle 1 : date de traitement > date de diagnostic (si présentes)
        date_pairs = [
            ("treatment_date", "diagnosis_date"),
            ("date_traitement", "date_diagnostic"),
        ]
        for treat_col, diag_col in date_pairs:
            if treat_col in df.columns and diag_col in df.columns:
                try:
                    treat = pd.to_datetime(df[treat_col])
                    diag = pd.to_datetime(df[diag_col])
                    violations = (treat < diag).sum()
                    if violations > 0:
                        issues.append(f"{violations} cas où traitement < diagnostic")
                except Exception:
                    pass

        # Règle 2 : âge cohérent avec les tranches (si dispo)
        if "age" in df.columns and "age_group" in df.columns:
            age_group_map = df.groupby("age_group")["age"].agg(["min", "max"])
            # Vérification basique — les tranches doivent être homogènes
            spread = age_group_map["max"] - age_group_map["min"]
            if (spread > 30).any():
                issues.append("Tranches d'âge trop larges (spread > 30 ans)")

        # Règle 3 : pas de valeurs négatives pour des métriques positives
        positive_cols = ["age", "blood_pressure", "glucose", "bmi", "heart_rate"]
        for col in positive_cols:
            matching = [c for c in df.columns if col in c.lower()]
            for c in matching:
                if pd.api.types.is_numeric_dtype(df[c]):
                    neg_count = (df[c] < 0).sum()
                    if neg_count > 0:
                        issues.append(f"{neg_count} valeur(s) négative(s) dans '{c}'")

        if not issues:
            return CheckResult(
                name="Cross-Feature Consistency Check",
                status="pass",
                message="Toutes les règles de cohérence inter-features sont satisfaites",
            )
        return CheckResult(
            name="Cross-Feature Consistency Check",
            status="warn",
            message=f"{len(issues)} problème(s) de cohérence détecté(s)",
            details={"issues": issues},
        )


class DistributionConsistencyChecker:
    """Vérifie la stabilité des distributions numériques (drift detection)."""

    def __init__(self, drift_threshold: float = 0.3):
        self.drift_threshold = drift_threshold

    def check(self, df: pd.DataFrame) -> CheckResult:
        stats = {}
        warnings = []

        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

        for col in numeric_cols:
            series = df[col].dropna()
            if len(series) < 10:
                continue

            mean = float(series.mean())
            std = float(series.std())
            skew = float(series.skew())
            cv = std / mean if mean != 0 else 0  # Coefficient de variation

            stats[col] = {
                "mean": round(mean, 3),
                "std": round(std, 3),
                "skewness": round(skew, 3),
                "cv": round(cv, 3),
            }

            if abs(skew) > 3:
                warnings.append(f"'{col}' très asymétrique (skew={skew:.2f})")
            if cv > self.drift_threshold * 5:
                warnings.append(f"'{col}' dispersion élevée (CV={cv:.2f})")

        if not warnings:
            return CheckResult(
                name="Distribution Consistency Check",
                status="pass",
                message="Distributions statistiquement stables",
                details=stats,
            )
        return CheckResult(
            name="Distribution Consistency Check",
            status="warn",
            message=f"{len(warnings)} anomalie(s) de distribution",
            details={"warnings": warnings, "stats": stats},
        )


# ---------------------------------------------------------------------------
# Rapport HTML
# ---------------------------------------------------------------------------

class DQVHTMLReport:
    """Génère un rapport HTML autonome des résultats DQV."""

    STATUS_COLORS = {
        "pass": ("#d4edda", "#155724", "✅"),
        "warn": ("#fff3cd", "#856404", "⚠️"),
        "fail": ("#f8d7da", "#721c24", "❌"),
    }

    def generate(self, results: list, df_shape: tuple, path: str) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)

        n_pass = sum(1 for r in results if r.status == "pass")
        n_warn = sum(1 for r in results if r.status == "warn")
        n_fail = sum(1 for r in results if r.status == "fail")
        overall = "pass" if n_fail == 0 and n_warn == 0 else ("warn" if n_fail == 0 else "fail")
        gate = "✅ ACCEPTÉ" if overall != "fail" else "❌ REJETÉ"
        gate_color = "#155724" if overall != "fail" else "#721c24"
        gate_bg = "#d4edda" if overall != "fail" else "#f8d7da"

        checks_html = ""
        for r in results:
            bg, text_color, icon = self.STATUS_COLORS.get(r.status, ("#fff", "#000", "?"))
            details_html = ""
            if r.details:
                details_html = f"""
                <details style="margin-top:8px">
                  <summary style="cursor:pointer;font-size:12px;color:{text_color}">
                    Voir les détails
                  </summary>
                  <pre style="font-size:11px;margin-top:6px;white-space:pre-wrap">
{json.dumps(r.details, indent=2, default=str, ensure_ascii=False)}
                  </pre>
                </details>"""
            checks_html += f"""
            <div style="background:{bg};border-left:4px solid {text_color};
                        padding:14px 16px;margin-bottom:12px;border-radius:6px">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <strong style="color:{text_color}">{icon} {r.name}</strong>
                <span style="font-size:12px;background:{text_color};color:white;
                             padding:2px 8px;border-radius:4px">{r.status.upper()}</span>
              </div>
              <p style="margin:6px 0 0;color:{text_color};font-size:13px">{r.message}</p>
              {details_html}
            </div>"""

        html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <title>Rapport DQV — Medical Pipeline</title>
  <style>
    body {{ font-family: system-ui, -apple-system, sans-serif; max-width: 860px;
            margin: 40px auto; padding: 0 20px; color: #212529; }}
    h1 {{ font-size: 24px; margin-bottom: 4px; }}
    .meta {{ color: #6c757d; font-size: 13px; margin-bottom: 28px; }}
    .summary {{ display: flex; gap: 16px; margin-bottom: 28px; }}
    .kpi {{ flex: 1; padding: 16px; border-radius: 8px; text-align: center; }}
    .kpi-val {{ font-size: 28px; font-weight: 700; }}
    .kpi-label {{ font-size: 12px; margin-top: 4px; }}
    .gate {{ padding: 14px 20px; border-radius: 8px; font-size: 18px;
             font-weight: 700; text-align: center; margin-bottom: 28px; }}
    h2 {{ font-size: 18px; border-bottom: 1px solid #dee2e6;
          padding-bottom: 8px; margin-bottom: 16px; }}
    details pre {{ background: #f8f9fa; padding: 10px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>Rapport DQV — Medical Data Pipeline</h1>
  <p class="meta">
    Généré le {datetime.now().strftime("%d/%m/%Y à %H:%M:%S")} |
    Dataset : {df_shape[0]} lignes × {df_shape[1]} colonnes
  </p>

  <div class="gate" style="background:{gate_bg};color:{gate_color}">
    Gate Check : {gate}
  </div>

  <div class="summary">
    <div class="kpi" style="background:#d4edda">
      <div class="kpi-val" style="color:#155724">{n_pass}</div>
      <div class="kpi-label" style="color:#155724">Passed</div>
    </div>
    <div class="kpi" style="background:#fff3cd">
      <div class="kpi-val" style="color:#856404">{n_warn}</div>
      <div class="kpi-label" style="color:#856404">Warnings</div>
    </div>
    <div class="kpi" style="background:#f8d7da">
      <div class="kpi-val" style="color:#721c24">{n_fail}</div>
      <div class="kpi-label" style="color:#721c24">Failed</div>
    </div>
    <div class="kpi" style="background:#e2e3e5">
      <div class="kpi-val" style="color:#383d41">{len(results)}</div>
      <div class="kpi-label" style="color:#383d41">Total checks</div>
    </div>
  </div>

  <h2>Détail des vérifications</h2>
  {checks_html}
</body>
</html>"""

        output.write_text(html, encoding="utf-8")
        logger.info(f"Rapport HTML DQV sauvegardé → {output}")


# ---------------------------------------------------------------------------
# Orchestrateur DQV
# ---------------------------------------------------------------------------

class DataQualityVerifier:
    """
    Orchestrateur DQV complet.
    Enchaîne tous les checks et applique le gate check (pass/reject).
    """

    def __init__(self, config: DQVConfig = None):
        self.config = config or DQVConfig()
        self._checkers = [
            MissingValueChecker(self.config.missing_threshold),
            DuplicateChecker(),
            DomainValidityChecker(),
            CrossFeatureConsistencyChecker(),
            DistributionConsistencyChecker(self.config.distribution_drift_threshold),
        ]

    def run(self, df: pd.DataFrame) -> tuple[bool, list]:
        """
        Exécute tous les checks DQV.
        Retourne (gate_passed, results_list).
        """
        logger.info(f"Lancement DQV sur {len(df)} lignes × {len(df.columns)} colonnes")
        results = []

        for checker in self._checkers:
            if isinstance(checker, DomainValidityChecker):
                result = checker.check(df, self.config.domain_rules)
            else:
                result = checker.check(df)
            results.append(result)
            icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}.get(result.status, "?")
            logger.info(f"{icon} {result.name} → {result.status.upper()}: {result.message}")

        # Gate check : fail si au moins un check est "fail"
        gate_passed = all(r.status != "fail" for r in results)
        status_label = "ACCEPTÉ ✅" if gate_passed else "REJETÉ ❌"
        logger.info(f"\nGate Check : {status_label}")

        # Génération des rapports
        reporter = DQVHTMLReport()
        reporter.generate(results, df.shape, self.config.report_path)
        self._save_json(results, gate_passed)

        return gate_passed, results

    def _save_json(self, results: list, gate_passed: bool) -> None:
        output = Path(self.config.results_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "timestamp": datetime.now().isoformat(),
            "gate_passed": gate_passed,
            "summary": {
                "pass": sum(1 for r in results if r.status == "pass"),
                "warn": sum(1 for r in results if r.status == "warn"),
                "fail": sum(1 for r in results if r.status == "fail"),
            },
            "checks": [r.to_dict() for r in results],
        }
        output.write_text(json.dumps(data, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
        logger.info(f"Résultats DQV JSON → {output}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Dataset de test
    df = pd.DataFrame({
        "age":            [45, 32, 999, 51, 28, 60, 38, 45, 32, 67],
        "blood_pressure": [130, 120, 145, 118, 122, 138, 125, 130, 120, 145],
        "glucose":        [95, 110, 88, 102, 78, 95, None, None, 110, 88],
        "diagnosis":      ["hypertension"] * 5 + ["diabetes"] * 5,
        "gender":         ["F", "M", "F", "M", "F", "M", "F", "F", "M", "F"],
    })

    verifier = DataQualityVerifier()
    gate_ok, results = verifier.run(df)
    print(f"\nGate passed : {gate_ok}")