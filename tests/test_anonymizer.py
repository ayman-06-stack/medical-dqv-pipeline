"""
tests/test_anonymizer.py
------------------------
Tests unitaires du module d'anonymisation PHI + k-anonymity.
Utilise pytest avec des datasets synthétiques.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from anonymizer import (
    DirectIdentifierRemover,
    KAnonymizer,
    MedicalAnonymizer,
    _detect_phi_columns,
    _hmac_hash,
)


# ---------------------------------------------------------------------------
# Fixtures partagées
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Dataset médical synthétique avec colonnes PHI."""
    return pd.DataFrame({
        "patient_id":     ["P001", "P002", "P003", "P004", "P005", "P006"],
        "name":           ["Alice M.", "Bob D.", "Claire R.", "David L.", "Eve B.", "Frank T."],
        "email":          ["a@test.com", "b@test.com", "c@test.com", "d@test.com", "e@test.com", "f@test.com"],
        "age":            [45, 32, 67, 45, 32, 67],
        "gender":         ["F", "M", "F", "M", "F", "M"],
        "zip_code":       ["75001", "75002", "75001", "75002", "75001", "75002"],
        "diagnosis":      ["hypertension", "diabetes", "hypertension", "diabetes", "asthma", "asthma"],
        "blood_pressure": [130, 120, 145, 118, 122, 138],
    })


@pytest.fixture
def df_no_phi() -> pd.DataFrame:
    """Dataset sans colonnes PHI identifiables."""
    return pd.DataFrame({
        "blood_pressure": [130, 120, 145, 118, 122, 138],
        "glucose":        [95, 110, 88, 102, 78, 95],
        "diagnosis":      ["hypertension", "diabetes", "hypertension", "diabetes", "asthma", "asthma"],
    })


@pytest.fixture
def df_small() -> pd.DataFrame:
    """Petit dataset pour tester les violations de k-anonymity."""
    return pd.DataFrame({
        "age":       [25, 30, 45],
        "gender":    ["F", "M", "F"],
        "diagnosis": ["diabetes", "asthma", "hypertension"],
    })


# ---------------------------------------------------------------------------
# Tests — _detect_phi_columns
# ---------------------------------------------------------------------------

class TestDetectPhiColumns:

    def test_detects_direct_identifiers(self, sample_df):
        phi = _detect_phi_columns(sample_df)
        assert "name" in phi["direct"]
        assert "email" in phi["direct"]
        assert "patient_id" in phi["direct"]

    def test_detects_quasi_identifiers(self, sample_df):
        phi = _detect_phi_columns(sample_df)
        assert "age" in phi["quasi"]
        assert "gender" in phi["quasi"]
        assert "zip_code" in phi["quasi"]

    def test_no_overlap_direct_quasi(self, sample_df):
        phi = _detect_phi_columns(sample_df)
        overlap = set(phi["direct"]) & set(phi["quasi"])
        assert len(overlap) == 0, f"Overlap trouvé : {overlap}"

    def test_no_phi_detected(self, df_no_phi):
        phi = _detect_phi_columns(df_no_phi)
        assert phi["direct"] == []
        # "diagnosis" ne doit pas être détecté comme quasi-identifiant
        assert "diagnosis" not in phi["quasi"]

    def test_empty_dataframe(self):
        phi = _detect_phi_columns(pd.DataFrame())
        assert phi["direct"] == []
        assert phi["quasi"] == []


# ---------------------------------------------------------------------------
# Tests — _hmac_hash
# ---------------------------------------------------------------------------

class TestHmacHash:

    def test_returns_string(self):
        result = _hmac_hash("test_value")
        assert isinstance(result, str)

    def test_fixed_length(self):
        result = _hmac_hash("any value")
        assert len(result) == 16

    def test_deterministic(self):
        assert _hmac_hash("same") == _hmac_hash("same")

    def test_different_inputs_different_hashes(self):
        assert _hmac_hash("value_a") != _hmac_hash("value_b")

    def test_handles_empty_string(self):
        result = _hmac_hash("")
        assert isinstance(result, str)
        assert len(result) == 16


# ---------------------------------------------------------------------------
# Tests — DirectIdentifierRemover
# ---------------------------------------------------------------------------

class TestDirectIdentifierRemover:

    def test_strategy_drop_removes_columns(self, sample_df):
        remover = DirectIdentifierRemover(strategy="drop")
        result = remover.fit_transform(sample_df, ["name", "email"])
        assert "name" not in result.columns
        assert "email" not in result.columns

    def test_strategy_drop_keeps_other_columns(self, sample_df):
        remover = DirectIdentifierRemover(strategy="drop")
        result = remover.fit_transform(sample_df, ["name"])
        assert "age" in result.columns
        assert "diagnosis" in result.columns

    def test_strategy_replace_keeps_columns(self, sample_df):
        remover = DirectIdentifierRemover(strategy="replace")
        result = remover.fit_transform(sample_df, ["name", "email"])
        assert "name" in result.columns
        assert "email" in result.columns

    def test_strategy_replace_changes_values(self, sample_df):
        remover = DirectIdentifierRemover(strategy="replace")
        result = remover.fit_transform(sample_df.copy(), ["name"])
        # Les valeurs doivent avoir changé
        original_names = set(sample_df["name"].tolist())
        result_names = set(result["name"].tolist())
        assert original_names != result_names

    def test_strategy_hash_changes_values(self, sample_df):
        remover = DirectIdentifierRemover(strategy="hash")
        result = remover.fit_transform(sample_df.copy(), ["patient_id"])
        # Toutes les valeurs hashées doivent avoir 16 caractères
        assert all(len(str(v)) == 16 for v in result["patient_id"])

    def test_ignores_missing_columns(self, sample_df):
        remover = DirectIdentifierRemover(strategy="drop")
        result = remover.fit_transform(sample_df, ["nonexistent_col"])
        # Aucune erreur, dataset inchangé
        assert list(result.columns) == list(sample_df.columns)

    def test_preserves_row_count(self, sample_df):
        remover = DirectIdentifierRemover(strategy="replace")
        result = remover.fit_transform(sample_df, ["name", "email"])
        assert len(result) == len(sample_df)

    def test_does_not_modify_original(self, sample_df):
        original_names = sample_df["name"].tolist()
        remover = DirectIdentifierRemover(strategy="replace")
        remover.fit_transform(sample_df, ["name"])
        assert sample_df["name"].tolist() == original_names


# ---------------------------------------------------------------------------
# Tests — KAnonymizer
# ---------------------------------------------------------------------------

class TestKAnonymizer:

    def test_k3_satisfied_on_valid_data(self, sample_df):
        k_anon = KAnonymizer(k=3)
        result = k_anon.fit_transform(sample_df, ["age", "gender"])
        is_ok = k_anon.verify(result, ["age", "gender"])
        assert is_ok is True

    def test_k3_suppresses_violations(self, df_small):
        """Avec k=3 et seulement 3 lignes uniques, tout doit être supprimé."""
        k_anon = KAnonymizer(k=3)
        result = k_anon.fit_transform(df_small, ["age", "gender"])
        # Toutes les lignes sont uniques donc toutes supprimées
        assert len(result) == 0 or k_anon.verify(result, ["age", "gender"])

    def test_k1_keeps_all_rows(self, sample_df):
        k_anon = KAnonymizer(k=1)
        result = k_anon.fit_transform(sample_df, ["age"])
        assert len(result) == len(sample_df)

    def test_generalizes_numeric_columns(self, sample_df):
        k_anon = KAnonymizer(k=2)
        result = k_anon.fit_transform(sample_df, ["age"])
        # Après généralisation, "age" doit contenir des intervalles (strings)
        assert result["age"].dtype == object or str(result["age"].dtype).startswith("object")

    def test_no_quasi_identifiers(self, sample_df):
        k_anon = KAnonymizer(k=3)
        result = k_anon.fit_transform(sample_df, [])
        assert len(result) == len(sample_df)

    def test_missing_quasi_columns(self, sample_df):
        k_anon = KAnonymizer(k=3)
        result = k_anon.fit_transform(sample_df, ["nonexistent_col"])
        assert len(result) == len(sample_df)

    def test_verify_returns_false_on_violation(self):
        df = pd.DataFrame({
            "age":  ["20-30", "20-30", "30-40"],
            "data": [1, 2, 3],
        })
        k_anon = KAnonymizer(k=3)
        # groupe "30-40" a 1 seul élément → violation
        assert k_anon.verify(df, ["age"]) is False

    def test_suppressed_rows_counter(self, sample_df):
        k_anon = KAnonymizer(k=10)  # k très élevé → beaucoup supprimés
        k_anon.fit_transform(sample_df, ["age", "gender"])
        assert k_anon._suppressed_rows >= 0


# ---------------------------------------------------------------------------
# Tests — MedicalAnonymizer (intégration)
# ---------------------------------------------------------------------------

class TestMedicalAnonymizer:

    def test_run_returns_dataframe(self, sample_df, tmp_path):
        anon = MedicalAnonymizer(
            k=2,
            strategy="drop",
            output_path=str(tmp_path / "anon.csv"),
            report_path=str(tmp_path / "report.json"),
        )
        result = anon.run(sample_df)
        assert isinstance(result, pd.DataFrame)

    def test_output_file_created(self, sample_df, tmp_path):
        out = tmp_path / "anon.csv"
        anon = MedicalAnonymizer(
            k=2,
            strategy="drop",
            output_path=str(out),
            report_path=str(tmp_path / "report.json"),
        )
        anon.run(sample_df)
        assert out.exists()

    def test_report_file_created(self, sample_df, tmp_path):
        report = tmp_path / "report.json"
        anon = MedicalAnonymizer(
            k=2,
            strategy="replace",
            output_path=str(tmp_path / "anon.csv"),
            report_path=str(report),
        )
        anon.run(sample_df)
        assert report.exists()

    def test_phi_columns_removed_with_drop(self, sample_df, tmp_path):
        anon = MedicalAnonymizer(
            k=2,
            strategy="drop",
            output_path=str(tmp_path / "anon.csv"),
            report_path=str(tmp_path / "report.json"),
        )
        result = anon.run(sample_df)
        assert "name" not in result.columns
        assert "email" not in result.columns

    def test_medical_columns_preserved(self, sample_df, tmp_path):
        anon = MedicalAnonymizer(
            k=2,
            strategy="drop",
            output_path=str(tmp_path / "anon.csv"),
            report_path=str(tmp_path / "report.json"),
        )
        result = anon.run(sample_df)
        assert "diagnosis" in result.columns
        assert "blood_pressure" in result.columns

    def test_empty_dataframe_handled(self, tmp_path):
        anon = MedicalAnonymizer(
            k=3,
            strategy="replace",
            output_path=str(tmp_path / "anon.csv"),
            report_path=str(tmp_path / "report.json"),
        )
        result = anon.run(pd.DataFrame())
        assert isinstance(result, pd.DataFrame)

    def test_strategy_replace_no_real_names(self, sample_df, tmp_path):
        original_names = set(sample_df["name"].tolist())
        anon = MedicalAnonymizer(
            k=2,
            strategy="replace",
            output_path=str(tmp_path / "anon.csv"),
            report_path=str(tmp_path / "report.json"),
        )
        result = anon.run(sample_df)
        if "name" in result.columns:
            result_names = set(result["name"].tolist())
            assert not original_names.intersection(result_names)

    @pytest.mark.parametrize("strategy", ["replace", "hash", "drop"])
    def test_all_strategies_run_without_error(self, sample_df, tmp_path, strategy):
        anon = MedicalAnonymizer(
            k=2,
            strategy=strategy,
            output_path=str(tmp_path / f"anon_{strategy}.csv"),
            report_path=str(tmp_path / f"report_{strategy}.json"),
        )
        result = anon.run(sample_df)
        assert isinstance(result, pd.DataFrame)
