"""
anonymizer.py
-------------
Module d'anonymisation des données médicales.
Gère la dé-identification des champs PHI et l'implémentation de k-anonymity.
"""

import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from faker import Faker

logger = logging.getLogger("anonymizer")
fake = Faker("fr_FR")

# ---------------------------------------------------------------------------
# Constantes — champs PHI (Protected Health Information)
# ---------------------------------------------------------------------------

PHI_DIRECT_IDENTIFIERS = [
    "name", "nom", "prenom", "first_name", "last_name",
    "email", "phone", "telephone", "address", "adresse",
    "ssn", "nss", "nin", "ip_address", "ip",
    "patient_id", "id_patient", "mrn",
]

PHI_QUASI_IDENTIFIERS = [
    "age", "gender", "sexe", "zip_code", "code_postal",
    "birth_date", "date_naissance", "ethnicity", "occupation",
]

AUDIT_KEY = os.environ.get("ANONYMIZER_HMAC_KEY", "medical_dqv_secret_key_change_me")


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------

def _hmac_hash(value: str) -> str:
    """Hash HMAC-SHA256 pour audit interne — non réversible publiquement."""
    return hmac.new(
        AUDIT_KEY.encode(),
        str(value).encode(),
        hashlib.sha256,
    ).hexdigest()[:16]


def _detect_phi_columns(df: pd.DataFrame) -> dict:
    """
    Détecte automatiquement les colonnes PHI dans le DataFrame.
    Retourne un dict { 'direct': [...], 'quasi': [...] }.
    """
    cols_lower = {col: col.lower().replace(" ", "_") for col in df.columns}

    def is_direct_match(col_l: str) -> bool:
        for phi in PHI_DIRECT_IDENTIFIERS:
            if phi == "ip":
                if col_l == "ip" or col_l.startswith("ip_") or col_l.endswith("_ip") or "_ip_" in col_l:
                    return True
            elif phi in col_l:
                return True
        return False

    direct = [
        col for col, col_l in cols_lower.items()
        if is_direct_match(col_l)
    ]
    quasi = [
        col for col, col_l in cols_lower.items()
        if any(phi in col_l for phi in PHI_QUASI_IDENTIFIERS)
        and col not in direct
    ]
    return {"direct": direct, "quasi": quasi}


# ---------------------------------------------------------------------------
# Suppression des identifiants directs
# ---------------------------------------------------------------------------

class DirectIdentifierRemover:
    """Supprime ou remplace les identifiants directs (PHI stricts)."""

    def __init__(self, strategy: str = "replace"):
        """
        strategy : 'drop'    → supprime la colonne entièrement
                   'replace' → remplace par des valeurs synthétiques (Faker)
                   'hash'    → remplace par un hash HMAC pour audit
        """
        self.strategy = strategy
        self._mapping: dict = {}

    def fit_transform(self, df: pd.DataFrame, columns: list) -> pd.DataFrame:
        df = df.copy()
        for col in columns:
            if col not in df.columns:
                continue

            if self.strategy == "drop":
                df.drop(columns=[col], inplace=True)
                logger.info(f"Colonne supprimée : {col}")

            elif self.strategy == "replace":
                replacements = self._generate_replacements(col, len(df))
                self._mapping[col] = {
                    str(orig): repl
                    for orig, repl in zip(df[col].astype(str), replacements)
                }
                df[col] = replacements
                logger.info(f"Colonne remplacée (synthétique) : {col}")

            elif self.strategy == "hash":
                df[col] = df[col].astype(str).apply(_hmac_hash)
                logger.info(f"Colonne hachée (HMAC) : {col}")

        return df

    def _generate_replacements(self, col_name: str, n: int) -> list:
        """Génère des valeurs synthétiques cohérentes avec le type de colonne."""
        col_l = col_name.lower()
        if any(k in col_l for k in ["name", "nom", "prenom"]):
            return [fake.name() for _ in range(n)]
        if any(k in col_l for k in ["email"]):
            return [fake.email() for _ in range(n)]
        if any(k in col_l for k in ["phone", "tel"]):
            return [fake.phone_number() for _ in range(n)]
        if any(k in col_l for k in ["address", "adresse"]):
            return [fake.address().replace("\n", ", ") for _ in range(n)]
        if any(k in col_l for k in ["ssn", "nss", "nin"]):
            return [fake.ssn() for _ in range(n)]
        if any(k in col_l for k in ["ip"]):
            return [fake.ipv4() for _ in range(n)]
        # Fallback : identifiant aléatoire
        return [f"ANON_{i:06d}" for i in range(n)]


# ---------------------------------------------------------------------------
# K-Anonymity
# ---------------------------------------------------------------------------

class KAnonymizer:
    """
    Implémente k-anonymity par généralisation des quasi-identifiants.
    Assure que chaque combinaison de QI apparaît au moins k fois.
    """

    def __init__(self, k: int = 3):
        self.k = k
        self._suppressed_rows = 0

    def fit_transform(self, df: pd.DataFrame, quasi_columns: list) -> pd.DataFrame:
        """
        Généralise les colonnes numériques en tranches (binning)
        et supprime les groupes qui ne satisfont pas k-anonymity.
        """
        df = df.copy()
        available_qi = [c for c in quasi_columns if c in df.columns]

        if not available_qi:
            logger.warning("Aucun quasi-identifiant trouvé — k-anonymity non appliquée")
            return df

        # Généralisation des numériques → tranches
        for col in available_qi:
            if pd.api.types.is_numeric_dtype(df[col]):
                df[col] = self._generalize_numeric(df[col])
                logger.info(f"Quasi-ID généralisé (tranches) : {col}")

        # Suppression des groupes qui violent k-anonymity
        before = len(df)
        group_sizes = df.groupby(available_qi)[available_qi[0]].transform("count")
        df = df[group_sizes >= self.k].copy()
        self._suppressed_rows = before - len(df)

        if self._suppressed_rows > 0:
            logger.warning(
                f"k-anonymity (k={self.k}) : {self._suppressed_rows} lignes supprimées "
                f"({self._suppressed_rows / before * 100:.1f}% du dataset)"
            )
        else:
            logger.info(f"k-anonymity (k={self.k}) satisfaite sans suppression")

        return df

    def verify(self, df: pd.DataFrame, quasi_columns: list) -> bool:
        """Vérifie que k-anonymity est bien respectée sur le DataFrame final."""
        available_qi = [c for c in quasi_columns if c in df.columns]
        if not available_qi:
            return True
        group_sizes = df.groupby(available_qi).size()
        violations = (group_sizes < self.k).sum()
        if violations > 0:
            logger.error(f"k-anonymity violée : {violations} groupe(s) < k={self.k}")
            return False
        logger.info(f"k-anonymity vérifiée (k={self.k}) — aucune violation")
        return True

    @staticmethod
    def _generalize_numeric(series: pd.Series, n_bins: int = 5) -> pd.Series:
        """Découpe une série numérique en n tranches égales (labels lisibles)."""
        try:
            return pd.cut(series, bins=n_bins, precision=0).astype(str)
        except Exception:
            return series.astype(str)


# ---------------------------------------------------------------------------
# Rapport d'anonymisation
# ---------------------------------------------------------------------------

class AnonymizationReport:
    """Génère et sauvegarde un rapport JSON de l'anonymisation effectuée."""

    def __init__(self):
        self._data: dict = {}

    def record(self, key: str, value) -> None:
        self._data[key] = value

    def save(self, path: str = "reports/anonymization_report.json") -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"Rapport d'anonymisation sauvegardé → {output}")

    def summary(self) -> str:
        lines = [
            "=" * 50,
            "  RAPPORT D'ANONYMISATION",
            "=" * 50,
        ]
        for k, v in self._data.items():
            lines.append(f"  {k:<35} {v}")
        lines.append("=" * 50)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Orchestrateur principal
# ---------------------------------------------------------------------------

class MedicalAnonymizer:
    """
    Orchestrateur complet d'anonymisation médicale.
    Enchaîne : détection PHI → suppression directe → k-anonymity → rapport.
    """

    def __init__(
        self,
        k: int = 3,
        strategy: str = "replace",
        output_path: str = "data/processed/medical_v1.0_anonymized.csv",
        report_path: str = "reports/anonymization_report.json",
    ):
        self.k = k
        self.strategy = strategy
        self.output_path = output_path
        self.report_path = report_path
        self._remover = DirectIdentifierRemover(strategy=strategy)
        self._k_anonymizer = KAnonymizer(k=k)
        self._report = AnonymizationReport()

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        """Pipeline complet d'anonymisation."""
        logger.info(f"Démarrage de l'anonymisation — {len(df)} lignes en entrée")
        self._report.record("input_rows", len(df))
        self._report.record("input_columns", list(df.columns))

        # 1. Détection automatique des colonnes PHI
        phi = _detect_phi_columns(df)
        logger.info(f"PHI directs détectés  : {phi['direct']}")
        logger.info(f"Quasi-identifiants     : {phi['quasi']}")
        self._report.record("phi_direct_columns", phi["direct"])
        self._report.record("quasi_identifier_columns", phi["quasi"])

        # 2. Suppression / remplacement des identifiants directs
        df = self._remover.fit_transform(df, phi["direct"])

        # 3. K-Anonymity sur les quasi-identifiants
        df = self._k_anonymizer.fit_transform(df, phi["quasi"])

        # 4. Vérification finale
        k_ok = self._k_anonymizer.verify(df, phi["quasi"])
        self._report.record("k_anonymity_satisfied", k_ok)
        self._report.record("k_value", self.k)
        self._report.record("rows_suppressed_k_anonymity", self._k_anonymizer._suppressed_rows)
        self._report.record("output_rows", len(df))
        self._report.record("output_columns", list(df.columns))
        self._report.record("anonymization_strategy", self.strategy)

        # 5. Sauvegarde
        self._save(df)
        self._report.save(self.report_path)
        print(self._report.summary())

        return df

    def _save(self, df: pd.DataFrame) -> None:
        output = Path(self.output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output, index=False)
        logger.info(f"Dataset anonymisé sauvegardé → {output}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sample = pd.DataFrame({
        "patient_id": ["P001", "P002", "P003", "P004", "P005"],
        "name": ["Alice Martin", "Bob Dupont", "Claire Durand", "David Leroy", "Eve Bernard"],
        "age": [45, 32, 67, 51, 28],
        "gender": ["F", "M", "F", "M", "F"],
        "zip_code": ["75001", "75002", "75001", "75002", "75001"],
        "diagnosis": ["hypertension", "diabetes", "hypertension", "asthma", "diabetes"],
        "blood_pressure": [130, 120, 145, 118, 122],
    })

    anonymizer = MedicalAnonymizer(k=3, strategy="replace")
    df_anon = anonymizer.run(sample)
    print(df_anon)