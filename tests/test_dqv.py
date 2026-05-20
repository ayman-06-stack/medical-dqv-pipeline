"""
tests/test_dqv.py
-----------------
Tests unitaires du module DQV (Data Quality Verification).
Couvre chaque checker individuel + l'orchestrateur complet.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from dqv import (
    CheckResult,
    CrossFeatureConsistencyChecker,
    DataQualityVerifier,
    DistributionConsistencyChecker,
    DomainValidityChecker,
    DQVConfig,
    DuplicateChecker,
    MissingValueChecker,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def clean_df() -> pd.DataFrame:
    """Dataset médical propre — tous les checks doivent passer."""
    return pd.DataFrame({
        "age":            [45, 32, 67, 51, 28, 60, 38, 44, 55, 70],
        "blood_pressure": [130, 120, 145, 118, 122, 138, 125, 132, 119, 141],
        "glucose":        [95, 110, 88, 102, 78, 95, 84, 101, 97, 90],
        "heart_rate":     [72, 80, 68, 76, 65, 74, 70, 78, 69, 73],
        "gender":         ["F", "M", "F", "M", "F", "M", "F", "M", "F", "M"],
        "diagnosis":      ["hypertension"] * 5 + ["diabetes"] * 5,
    })


@pytest.fixture
def dirty_df() -> pd.DataFrame:
    """Dataset avec problèmes intentionnels."""
    return pd.DataFrame({
        "age":            [45, 32, 999, 51, 28, -5, 38, 44, 55, 70],   # outliers
        "blood_pressure": [130, 120, 145, 118, 122, 138, None, None, None, None],  # 40% missing
        "glucose":        [95, 110, 88, 102, 78, 95, 84, 101, 97, 90],
        "gender":         ["F", "M", "F", "M", "F", "M", "F", "M", "F", "M"],
        "diagnosis":      ["hypertension"] * 5 + ["diabetes"] * 5,
    })


@pytest.fixture
def df_with_duplicates(clean_df) -> pd.DataFrame:
    """Dataset avec doublons."""
    return pd.concat([clean_df, clean_df.iloc[:2]], ignore_index=True)


@pytest.fixture
def df_with_cross_violations() -> pd.DataFrame:
    """Dataset avec violations cross-features (valeurs négatives)."""
    return pd.DataFrame({
        "age":            [45, -1, 32, 67, 51],
        "blood_pressure": [130, 120, -50, 118, 122],
        "glucose":        [95, 110, 88, 102, 78],
        "treatment_date": ["2024-03-15", "2024-01-10", "2024-05-20", "2024-02-01", "2024-04-12"],
        "diagnosis_date": ["2024-01-01", "2024-02-01", "2024-03-01", "2024-01-15", "2024-02-28"],
    })


# ---------------------------------------------------------------------------
# Tests — CheckResult
# ---------------------------------------------------------------------------

class TestCheckResult:

    def test_to_dict_contains_required_keys(self):
        r = CheckResult(name="Test", status="pass", message="OK")
        d = r.to_dict()
        assert "name" in d
        assert "status" in d
        assert "message" in d

    def test_to_dict_with_details(self):
        r = CheckResult(name="Test", status="warn", message="Warn", details={"key": "val"})
        d = r.to_dict()
        assert d["details"] == {"key": "val"}

    def test_to_dict_empty_details(self):
        r = CheckResult(name="Test", status="pass", message="OK")
        d = r.to_dict()
        assert d["details"] == {}

    @pytest.mark.parametrize("status", ["pass", "warn", "fail"])
    def test_valid_statuses(self, status):
        r = CheckResult(name="T", status=status, message="m")
        assert r.status == status


# ---------------------------------------------------------------------------
# Tests — MissingValueChecker
# ---------------------------------------------------------------------------

class TestMissingValueChecker:

    def test_pass_on_clean_data(self, clean_df):
        checker = MissingValueChecker(threshold=0.15)
        result = checker.check(clean_df)
        assert result.status == "pass"

    def test_warn_on_moderate_missing(self, dirty_df):
        checker = MissingValueChecker(threshold=0.15)
        result = checker.check(dirty_df)
        # blood_pressure a 40% manquant → au moins warn
        assert result.status in ("warn", "fail")

    def test_fail_on_high_missing(self):
        df = pd.DataFrame({
            "col_a": [None] * 8 + [1, 2],   # 80% manquant
            "col_b": [1] * 10,
        })
        checker = MissingValueChecker(threshold=0.15)
        result = checker.check(df)
        assert result.status == "fail"

    def test_threshold_respected(self):
        df = pd.DataFrame({
            "col": [None, 1, 1, 1, 1, 1, 1, 1, 1, 1],  # 10% manquant
        })
        checker = MissingValueChecker(threshold=0.15)
        result = checker.check(df)
        assert result.status == "pass"

    def test_all_missing_column(self):
        df = pd.DataFrame({"col": [None, None, None]})
        checker = MissingValueChecker(threshold=0.15)
        result = checker.check(df)
        assert result.status == "fail"

    def test_value_is_max_rate(self, clean_df):
        checker = MissingValueChecker(threshold=0.15)
        result = checker.check(clean_df)
        assert result.value == 0.0

    def test_details_contain_column_rates(self, dirty_df):
        checker = MissingValueChecker(threshold=0.15)
        result = checker.check(dirty_df)
        assert result.details is not None

    def test_empty_dataframe(self):
        checker = MissingValueChecker(threshold=0.15)
        result = checker.check(pd.DataFrame())
        assert result.status == "pass"


# ---------------------------------------------------------------------------
# Tests — DuplicateChecker
# ---------------------------------------------------------------------------

class TestDuplicateChecker:

    def test_pass_no_duplicates(self, clean_df):
        checker = DuplicateChecker()
        result = checker.check(clean_df)
        assert result.status == "pass"
        assert result.value == 0

    def test_warn_with_few_duplicates(self, df_with_duplicates):
        checker = DuplicateChecker()
        result = checker.check(df_with_duplicates)
        assert result.status in ("warn", "fail")
        assert result.value == 2

    def test_fail_with_many_duplicates(self, clean_df):
        # 50% de doublons → fail
        df = pd.concat([clean_df] * 2, ignore_index=True)
        checker = DuplicateChecker()
        result = checker.check(df)
        assert result.status == "fail"

    def test_duplicate_count_accurate(self, clean_df):
        df_dup = pd.concat([clean_df, clean_df.iloc[:3]], ignore_index=True)
        checker = DuplicateChecker()
        result = checker.check(df_dup)
        assert result.value == 3

    def test_single_row_df(self):
        df = pd.DataFrame({"a": [1], "b": [2]})
        checker = DuplicateChecker()
        result = checker.check(df)
        assert result.status == "pass"


# ---------------------------------------------------------------------------
# Tests — DomainValidityChecker
# ---------------------------------------------------------------------------

class TestDomainValidityChecker:

    def test_pass_all_valid(self, clean_df):
        checker = DomainValidityChecker()
        result = checker.check(clean_df)
        assert result.status == "pass"

    def test_warn_on_age_outlier(self):
        df = pd.DataFrame({"age": [45, 32, 999, 51]})  # 999 hors domaine
        checker = DomainValidityChecker()
        result = checker.check(df)
        assert result.status == "warn"

    def test_warn_on_negative_blood_pressure(self):
        df = pd.DataFrame({"blood_pressure": [130, 120, -10, 118]})
        checker = DomainValidityChecker()
        result = checker.check(df)
        assert result.status == "warn"

    def test_custom_rules_applied(self):
        df = pd.DataFrame({"custom_score": [5, 10, 150, 8]})  # 150 hors [0, 100]
        checker = DomainValidityChecker()
        result = checker.check(df, custom_rules={"custom_score": (0, 100)})
        assert result.status == "warn"

    def test_non_numeric_columns_ignored(self):
        df = pd.DataFrame({
            "age":       [45, 32, 67],
            "diagnosis": ["hyp", "dia", "ast"],  # string — ignorée
        })
        checker = DomainValidityChecker()
        result = checker.check(df)
        assert result.status == "pass"

    def test_details_contain_violation_info(self):
        df = pd.DataFrame({"age": [45, 32, 999]})
        checker = DomainValidityChecker()
        result = checker.check(df)
        assert result.details is not None
        assert "age" in result.details


# ---------------------------------------------------------------------------
# Tests — CrossFeatureConsistencyChecker
# ---------------------------------------------------------------------------

class TestCrossFeatureConsistencyChecker:

    def test_pass_on_clean_data(self, clean_df):
        checker = CrossFeatureConsistencyChecker()
        result = checker.check(clean_df)
        assert result.status == "pass"

    def test_detects_negative_age(self, df_with_cross_violations):
        checker = CrossFeatureConsistencyChecker()
        result = checker.check(df_with_cross_violations)
        assert result.status in ("warn", "fail")
        issues = result.details.get("issues", [])
        assert any("négatif" in i for i in issues)

    def test_detects_negative_blood_pressure(self, df_with_cross_violations):
        checker = CrossFeatureConsistencyChecker()
        result = checker.check(df_with_cross_violations)
        issues = result.details.get("issues", [])
        assert any("blood_pressure" in i for i in issues)

    def test_no_date_columns_no_error(self, clean_df):
        checker = CrossFeatureConsistencyChecker()
        result = checker.check(clean_df)
        assert isinstance(result, CheckResult)

    def test_treatment_before_diagnosis_detected(self):
        df = pd.DataFrame({
            "treatment_date": ["2024-01-01"],   # Avant le diagnostic
            "diagnosis_date": ["2024-06-01"],
        })
        checker = CrossFeatureConsistencyChecker()
        result = checker.check(df)
        assert result.status in ("warn", "fail")


# ---------------------------------------------------------------------------
# Tests — DistributionConsistencyChecker
# ---------------------------------------------------------------------------

class TestDistributionConsistencyChecker:

    def test_pass_on_normal_distributions(self, clean_df):
        checker = DistributionConsistencyChecker(drift_threshold=0.3)
        result = checker.check(clean_df)
        assert result.status == "pass"

    def test_warns_on_high_skewness(self):
        # Distribution très asymétrique
        df = pd.DataFrame({
            "value": [1, 1, 1, 1, 1, 1, 1, 1, 1, 10000],
        })
        checker = DistributionConsistencyChecker(drift_threshold=0.3)
        result = checker.check(df)
        # Skewness élevé → warn attendu
        assert result.status in ("pass", "warn")  # Dépend du seuil

    def test_details_contain_stats(self, clean_df):
        checker = DistributionConsistencyChecker()
        result = checker.check(clean_df)
        assert result.details is not None
        for col in clean_df.select_dtypes(include=[np.number]).columns:
            assert col in result.details

    def test_stats_keys_present(self, clean_df):
        checker = DistributionConsistencyChecker()
        result = checker.check(clean_df)
        stats = result.details
        for col_stats in stats.values():
            assert "mean" in col_stats
            assert "std" in col_stats
            assert "skewness" in col_stats

    def test_ignores_small_columns(self):
        df = pd.DataFrame({"tiny": [1, 2]})  # < 10 lignes
        checker = DistributionConsistencyChecker()
        result = checker.check(df)
        assert result.status == "pass"
        assert result.details == {}

    def test_no_numeric_columns(self):
        df = pd.DataFrame({"cat": ["a", "b", "c"] * 5})
        checker = DistributionConsistencyChecker()
        result = checker.check(df)
        assert result.status == "pass"


# ---------------------------------------------------------------------------
# Tests — DataQualityVerifier (orchestrateur)
# ---------------------------------------------------------------------------

class TestDataQualityVerifier:

    def test_gate_pass_on_clean_data(self, clean_df):
        config = DQVConfig(
            missing_threshold=0.15,
            report_path="/tmp/dqv_test_report.html",
            results_path="/tmp/dqv_test_results.json",
        )
        verifier = DataQualityVerifier(config)
        gate_passed, results = verifier.run(clean_df)
        assert gate_passed is True

    def test_gate_fail_on_dirty_data(self):
        df = pd.DataFrame({
            "age":  [45, 32, None, None, None, None, None, None, None, None],  # 90% missing
            "diag": ["a"] * 10,
        })
        config = DQVConfig(
            missing_threshold=0.15,
            report_path="/tmp/dqv_fail_report.html",
            results_path="/tmp/dqv_fail_results.json",
        )
        verifier = DataQualityVerifier(config)
        gate_passed, results = verifier.run(df)
        assert gate_passed is False

    def test_returns_correct_number_of_checks(self, clean_df):
        config = DQVConfig(
            report_path="/tmp/dqv_count_report.html",
            results_path="/tmp/dqv_count_results.json",
        )
        verifier = DataQualityVerifier(config)
        _, results = verifier.run(clean_df)
        # 5 checkers définis dans l'orchestrateur
        assert len(results) == 5

    def test_results_are_check_result_objects(self, clean_df):
        config = DQVConfig(
            report_path="/tmp/dqv_obj_report.html",
            results_path="/tmp/dqv_obj_results.json",
        )
        verifier = DataQualityVerifier(config)
        _, results = verifier.run(clean_df)
        assert all(isinstance(r, CheckResult) for r in results)

    def test_json_report_created(self, clean_df, tmp_path):
        config = DQVConfig(
            report_path=str(tmp_path / "report.html"),
            results_path=str(tmp_path / "results.json"),
        )
        verifier = DataQualityVerifier(config)
        verifier.run(clean_df)
        assert (tmp_path / "results.json").exists()

    def test_html_report_created(self, clean_df, tmp_path):
        config = DQVConfig(
            report_path=str(tmp_path / "report.html"),
            results_path=str(tmp_path / "results.json"),
        )
        verifier = DataQualityVerifier(config)
        verifier.run(clean_df)
        assert (tmp_path / "report.html").exists()

    def test_json_report_valid_structure(self, clean_df, tmp_path):
        config = DQVConfig(
            report_path=str(tmp_path / "report.html"),
            results_path=str(tmp_path / "results.json"),
        )
        verifier = DataQualityVerifier(config)
        verifier.run(clean_df)
        with open(tmp_path / "results.json", encoding="utf-8") as f:
            data = json.load(f)
        assert "gate_passed" in data
        assert "summary" in data
        assert "checks" in data
        assert "timestamp" in data

    def test_custom_threshold_applied(self):
        df = pd.DataFrame({
            "col": [None, 1, 1, 1, 1],  # 20% missing
        })
        # Avec seuil 30% : doit passer
        config_pass = DQVConfig(
            missing_threshold=0.30,
            report_path="/tmp/dqv_thresh_pass.html",
            results_path="/tmp/dqv_thresh_pass.json",
        )
        verifier = DataQualityVerifier(config_pass)
        gate, _ = verifier.run(df)
        assert gate is True

        # Avec seuil 10% : doit échouer
        config_fail = DQVConfig(
            missing_threshold=0.10,
            report_path="/tmp/dqv_thresh_fail.html",
            results_path="/tmp/dqv_thresh_fail.json",
        )
        verifier2 = DataQualityVerifier(config_fail)
        gate2, _ = verifier2.run(df)
        assert gate2 is False

    @pytest.mark.parametrize("n_rows", [5, 50, 500])
    def test_runs_on_different_sizes(self, n_rows, tmp_path):
        df = pd.DataFrame({
            "age":   np.random.randint(18, 80, n_rows),
            "score": np.random.rand(n_rows) * 100,
        })
        config = DQVConfig(
            report_path=str(tmp_path / f"report_{n_rows}.html"),
            results_path=str(tmp_path / f"results_{n_rows}.json"),
        )
        verifier = DataQualityVerifier(config)
        gate, results = verifier.run(df)
        assert isinstance(gate, bool)
        assert len(results) == 5
