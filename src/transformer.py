"""
transformer.py
--------------
Module de transformation des données médicales.
Encodage catégoriel, normalisation, gestion des outliers, pipeline sklearn.
"""

import logging
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import (
    LabelEncoder,
    OneHotEncoder,
    StandardScaler,
    MinMaxScaler,
)

logger = logging.getLogger("transformer")


# ---------------------------------------------------------------------------
# Transformers personnalisés (compatibles sklearn Pipeline)
# ---------------------------------------------------------------------------

class OutlierHandler(BaseEstimator, TransformerMixin):
    """
    Gestion des outliers par méthode IQR (Interquartile Range).
    Remplace les valeurs extrêmes par les bornes de l'IQR étendu.
    """

    def __init__(self, factor: float = 1.5, strategy: str = "clip"):
        """
        factor   : multiplicateur IQR (1.5 standard, 3.0 extrême)
        strategy : 'clip'   → plafonne aux bornes IQR
                   'median' → remplace par la médiane
                   'drop'   → retourne un masque (utilisé dans pipeline)
        """
        self.factor = factor
        self.strategy = strategy
        self._bounds: dict = {}

    def fit(self, X: pd.DataFrame, y=None):
        numeric_cols = X.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            q1 = X[col].quantile(0.25)
            q3 = X[col].quantile(0.75)
            iqr = q3 - q1
            self._bounds[col] = (
                q1 - self.factor * iqr,
                q3 + self.factor * iqr,
            )
        return self

    def transform(self, X: pd.DataFrame, y=None) -> pd.DataFrame:
        X = X.copy()
        for col, (lower, upper) in self._bounds.items():
            if col not in X.columns:
                continue
            n_outliers = ((X[col] < lower) | (X[col] > upper)).sum()
            if n_outliers > 0:
                logger.info(f"Outliers traités dans '{col}' : {n_outliers} valeur(s) [{self.strategy}]")

            if self.strategy == "clip":
                X[col] = X[col].clip(lower=lower, upper=upper)
            elif self.strategy == "median":
                median_val = X[col].median()
                X[col] = X[col].where((X[col] >= lower) & (X[col] <= upper), median_val)

        return X


class DateFormatter(BaseEstimator, TransformerMixin):
    """
    Formate les colonnes de dates et extrait des features temporelles
    (année, mois, jour, âge en jours depuis référence).
    """

    DATE_KEYWORDS = ["date", "birth", "admission", "discharge", "created"]

    def __init__(self, extract_features: bool = True):
        self.extract_features = extract_features
        self._date_cols: list = []

    def fit(self, X: pd.DataFrame, y=None):
        self._date_cols = [
            col for col in X.columns
            if any(kw in col.lower() for kw in self.DATE_KEYWORDS)
        ]
        return self

    def transform(self, X: pd.DataFrame, y=None) -> pd.DataFrame:
        X = X.copy()
        for col in self._date_cols:
            if col not in X.columns:
                continue
            try:
                X[col] = pd.to_datetime(X[col], errors="coerce")
                if self.extract_features:
                    X[f"{col}_year"] = X[col].dt.year
                    X[f"{col}_month"] = X[col].dt.month
                    X[f"{col}_dayofweek"] = X[col].dt.dayofweek
                X[col] = X[col].astype(str)
                logger.info(f"Date formatée + features extraites : '{col}'")
            except Exception as e:
                logger.warning(f"Impossible de parser la date '{col}' : {e}")
        return X


class MissingValueImputer(BaseEstimator, TransformerMixin):
    """
    Imputation des valeurs manquantes :
    - Numériques  → médiane
    - Catégorielles → mode (valeur la plus fréquente)
    """

    def __init__(self):
        self._medians: dict = {}
        self._modes: dict = {}

    def fit(self, X: pd.DataFrame, y=None):
        for col in X.select_dtypes(include=[np.number]).columns:
            self._medians[col] = X[col].median()
        for col in X.select_dtypes(include=["object", "category"]).columns:
            mode = X[col].mode()
            self._modes[col] = mode[0] if len(mode) > 0 else "UNKNOWN"
        return self

    def transform(self, X: pd.DataFrame, y=None) -> pd.DataFrame:
        X = X.copy()
        for col, val in self._medians.items():
            if col in X.columns and X[col].isnull().any():
                filled = X[col].isnull().sum()
                X[col] = X[col].fillna(val)
                logger.debug(f"Imputation médiane '{col}' : {filled} valeur(s)")
        for col, val in self._modes.items():
            if col in X.columns and X[col].isnull().any():
                filled = X[col].isnull().sum()
                X[col] = X[col].fillna(val)
                logger.debug(f"Imputation mode '{col}' : {filled} valeur(s)")
        return X


class CategoricalEncoder(BaseEstimator, TransformerMixin):
    """
    Encodage des variables catégorielles.
    - OHE (OneHotEncoder) pour colonnes à faible cardinalité (≤ max_ohe_cardinality)
    - Label Encoding pour colonnes à haute cardinalité
    """

    def __init__(self, max_ohe_cardinality: int = 5, drop: str = "first"):
        self.max_ohe_cardinality = max_ohe_cardinality
        self.drop = drop
        self._ohe_cols: list = []
        self._label_cols: list = []
        self._ohe: Optional[OneHotEncoder] = None
        self._label_encoders: dict = {}
        self._ohe_feature_names: list = []

    def fit(self, X: pd.DataFrame, y=None):
        cat_cols = X.select_dtypes(include=["object", "category"]).columns.tolist()
        for col in cat_cols:
            cardinality = X[col].nunique()
            if cardinality <= self.max_ohe_cardinality:
                self._ohe_cols.append(col)
            else:
                self._label_cols.append(col)

        if self._ohe_cols:
            self._ohe = OneHotEncoder(
                drop=self.drop, sparse_output=False, handle_unknown="ignore"
            )
            self._ohe.fit(X[self._ohe_cols])
            self._ohe_feature_names = self._ohe.get_feature_names_out(self._ohe_cols).tolist()
            logger.info(f"OHE configuré pour : {self._ohe_cols}")

        for col in self._label_cols:
            le = LabelEncoder()
            le.fit(X[col].astype(str))
            self._label_encoders[col] = le
            logger.info(f"Label Encoding configuré pour : '{col}' ({X[col].nunique()} modalités)")

        return self

    def transform(self, X: pd.DataFrame, y=None) -> pd.DataFrame:
        X = X.copy()

        if self._ohe and self._ohe_cols:
            ohe_array = self._ohe.transform(X[self._ohe_cols])
            ohe_df = pd.DataFrame(
                ohe_array,
                columns=self._ohe_feature_names,
                index=X.index,
            )
            X = X.drop(columns=self._ohe_cols)
            X = pd.concat([X, ohe_df], axis=1)

        for col, le in self._label_encoders.items():
            if col in X.columns:
                # Gérer les labels inconnus (transform robuste)
                X[col] = X[col].astype(str).apply(
                    lambda v: le.transform([v])[0] if v in le.classes_ else -1
                )

        return X


class FeatureScaler(BaseEstimator, TransformerMixin):
    """
    Normalisation des features numériques.
    Supports StandardScaler (z-score) et MinMaxScaler (0-1).
    """

    def __init__(self, method: str = "standard"):
        """
        method : 'standard' → StandardScaler (mean=0, std=1)
                 'minmax'   → MinMaxScaler (0-1)
        """
        self.method = method
        self._scaler = None
        self._numeric_cols: list = []

    def fit(self, X: pd.DataFrame, y=None):
        self._numeric_cols = X.select_dtypes(include=[np.number]).columns.tolist()
        if not self._numeric_cols:
            return self
        self._scaler = (
            StandardScaler() if self.method == "standard" else MinMaxScaler()
        )
        self._scaler.fit(X[self._numeric_cols])
        logger.info(f"Scaler ({self.method}) fit sur : {self._numeric_cols}")
        return self

    def transform(self, X: pd.DataFrame, y=None) -> pd.DataFrame:
        X = X.copy()
        if self._scaler and self._numeric_cols:
            available = [c for c in self._numeric_cols if c in X.columns]
            X[available] = self._scaler.transform(X[available])
        return X


# ---------------------------------------------------------------------------
# Pipeline complet
# ---------------------------------------------------------------------------

class MedicalTransformer:
    """
    Orchestrateur de transformation complet.
    Construit et exécute un pipeline sklearn de bout en bout.
    """

    def __init__(
        self,
        outlier_factor: float = 1.5,
        scaler_method: str = "standard",
        max_ohe_cardinality: int = 5,
        pipeline_path: str = "data/processed/transformer_pipeline.pkl",
    ):
        self.pipeline_path = pipeline_path
        self._pipeline = Pipeline([
            ("imputer",  MissingValueImputer()),
            ("dates",    DateFormatter(extract_features=True)),
            ("outliers", OutlierHandler(factor=outlier_factor, strategy="clip")),
            ("encoder",  CategoricalEncoder(max_ohe_cardinality=max_ohe_cardinality)),
            ("scaler",   FeatureScaler(method=scaler_method)),
        ])

    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Entraîne le pipeline et transforme le dataset."""
        logger.info(f"Transformation — entrée : {df.shape}")
        result = self._pipeline.fit_transform(df)

        # Reconstruire en DataFrame si le pipeline retourne un array
        if isinstance(result, np.ndarray):
            result = pd.DataFrame(result)

        logger.info(f"Transformation — sortie : {result.shape}")
        self._save_pipeline()
        return result

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Applique le pipeline entraîné sur de nouvelles données."""
        result = self._pipeline.transform(df)
        if isinstance(result, np.ndarray):
            result = pd.DataFrame(result)
        return result

    def _save_pipeline(self) -> None:
        output = Path(self.pipeline_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self._pipeline, output)
        logger.info(f"Pipeline sklearn sauvegardé → {output}")

    @classmethod
    def load_pipeline(cls, path: str) -> Pipeline:
        """Charge un pipeline sklearn sérialisé."""
        pipeline = joblib.load(path)
        logger.info(f"Pipeline chargé depuis {path}")
        return pipeline

    def get_feature_names(self) -> list:
        """Retourne les noms des features après transformation."""
        try:
            encoder = self._pipeline.named_steps["encoder"]
            return encoder._ohe_feature_names + encoder._label_cols
        except Exception:
            return []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    df = pd.DataFrame({
        "age":            [45, 32, 67, 51, 28, 60, 38, 45, 32, 67],
        "blood_pressure": [130, 120, 145, 118, 122, 138, 125, 130, 120, 999],
        "glucose":        [95, 110, None, 102, 78, 95, None, 88, 110, 88],
        "diagnosis":      ["hypertension", "diabetes", "hypertension",
                           "diabetes", "asthma", "hypertension",
                           "diabetes", "asthma", "hypertension", "diabetes"],
        "gender":         ["F", "M", "F", "M", "F", "M", "F", "F", "M", "F"],
    })

    transformer = MedicalTransformer(outlier_factor=1.5, scaler_method="standard")
    df_transformed = transformer.fit_transform(df)
    print(df_transformed.head())
    print(f"\nShape finale : {df_transformed.shape}")