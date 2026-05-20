"""
notebooks/01_eda.py
--------------------
Analyse Exploratoire des Données (EDA) — équivalent Python du notebook Jupyter.
Exécuter avec : python notebooks/01_eda.py
Ou convertir en notebook : jupytext --to notebook notebooks/01_eda.py
"""

# %% [markdown]
# # 📊 Analyse Exploratoire — Medical DQV Pipeline
# Ce script explore le dataset médical brut avant traitement.
# Il guide les choix de nettoyage et d'anonymisation.

# %% Imports
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Style global
plt.style.use("seaborn-v0_8-whitegrid")
sns.set_palette("husl")
FIGSIZE = (12, 5)

# %% [markdown]
# ## 1. Chargement des données

# %% Chargement
DATA_PATH = "data/raw/medical_raw.csv"

def load_data(path: str) -> pd.DataFrame:
    """Charge le dataset brut avec gestion des erreurs."""
    p = Path(path)
    if not p.exists():
        print(f"⚠️  Fichier introuvable : {path}")
        print("   Lancez d'abord le scraper : python src/scraper.py")
        # Dataset synthétique pour la démonstration
        np.random.seed(42)
        n = 150
        return pd.DataFrame({
            "age":            np.random.randint(18, 90, n),
            "gender":         np.random.choice(["M", "F"], n),
            "blood_pressure": np.random.randint(90, 180, n),
            "glucose":        np.random.randint(70, 200, n),
            "heart_rate":     np.random.randint(55, 110, n),
            "bmi":            np.round(np.random.uniform(18, 40, n), 1),
            "diagnosis":      np.random.choice(["hypertension", "diabetes", "asthma", "healthy"], n),
            "name":           [f"Patient_{i:03d}" for i in range(n)],
            "treatment_date": pd.date_range("2023-01-01", periods=n, freq="2D").astype(str),
        })
    df = pd.read_csv(p)
    print(f"✅ Dataset chargé : {df.shape[0]} lignes × {df.shape[1]} colonnes")
    return df

df = load_data(DATA_PATH)


# %% [markdown]
# ## 2. Aperçu général

# %% Aperçu
print("\n" + "="*55)
print("  APERÇU DU DATASET")
print("="*55)
print(df.head(5).to_string())
print(f"\nShape : {df.shape}")
print(f"Colonnes : {list(df.columns)}")
print(f"\nTypes de données :")
print(df.dtypes.to_string())


# %% [markdown]
# ## 3. Statistiques descriptives

# %% Stats
print("\n" + "="*55)
print("  STATISTIQUES DESCRIPTIVES")
print("="*55)
desc = df.describe(include="all").T
desc["missing_%"] = (df.isnull().mean() * 100).round(2)
print(desc.to_string())


# %% [markdown]
# ## 4. Analyse des valeurs manquantes

# %% Valeurs manquantes
def plot_missing(df: pd.DataFrame) -> None:
    missing = df.isnull().mean().sort_values(ascending=False)
    missing = missing[missing > 0]

    if missing.empty:
        print("✅ Aucune valeur manquante détectée.")
        return

    fig, axes = plt.subplots(1, 2, figsize=FIGSIZE)

    # Barplot
    colors = ["#dc3545" if v > 0.15 else "#ffc107" if v > 0.05 else "#28a745"
              for v in missing.values]
    axes[0].bar(missing.index, missing.values * 100, color=colors)
    axes[0].axhline(y=15, color="red", linestyle="--", label="Seuil 15%")
    axes[0].set_title("Taux de valeurs manquantes par colonne (%)")
    axes[0].set_ylabel("Taux manquant (%)")
    axes[0].tick_params(axis="x", rotation=45)
    axes[0].legend()

    # Heatmap
    sns.heatmap(
        df.isnull().T,
        cbar=False,
        ax=axes[1],
        cmap=["#e8f5e9", "#ef9a9a"],
        yticklabels=True,
    )
    axes[1].set_title("Carte des valeurs manquantes")
    axes[1].set_xlabel("Index de ligne")

    plt.tight_layout()
    Path("reports").mkdir(exist_ok=True)
    plt.savefig("reports/eda_missing_values.png", dpi=150, bbox_inches="tight")
    plt.show()
    print(f"\nColonnes avec valeurs manquantes :")
    for col, rate in missing.items():
        status = "❌ CRITIQUE" if rate > 0.30 else "⚠️ ATTENTION" if rate > 0.15 else "✅ OK"
        print(f"  {col:<25} {rate*100:.1f}%  {status}")

plot_missing(df)


# %% [markdown]
# ## 5. Distributions des variables numériques

# %% Distributions
def plot_distributions(df: pd.DataFrame) -> None:
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if not num_cols:
        print("Aucune colonne numérique.")
        return

    n_cols = 3
    n_rows = int(np.ceil(len(num_cols) / n_cols))
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(15, n_rows * 3.5))
    axes = axes.flatten() if n_rows > 1 else [axes] if n_cols == 1 else axes.flatten()

    for i, col in enumerate(num_cols):
        ax = axes[i]
        data = df[col].dropna()

        # Histogramme + KDE
        ax.hist(data, bins=25, color="#1D9E75", alpha=0.6, edgecolor="white", density=True)
        try:
            from scipy.stats import gaussian_kde
            kde = gaussian_kde(data)
            x = np.linspace(data.min(), data.max(), 200)
            ax.plot(x, kde(x), color="#0F6E56", linewidth=2)
        except Exception:
            pass

        ax.axvline(data.mean(), color="red", linestyle="--", linewidth=1.5,
                   label=f"Moy: {data.mean():.1f}")
        ax.axvline(data.median(), color="orange", linestyle=":", linewidth=1.5,
                   label=f"Méd: {data.median():.1f}")
        ax.set_title(f"{col}\n(skew={data.skew():.2f}, n={len(data)})", fontsize=11)
        ax.legend(fontsize=8)
        ax.set_xlabel("")

    # Cacher les axes vides
    for j in range(len(num_cols), len(axes)):
        axes[j].set_visible(False)

    plt.suptitle("Distributions des variables numériques", fontsize=14, fontweight="bold", y=1.01)
    plt.tight_layout()
    plt.savefig("reports/eda_distributions.png", dpi=150, bbox_inches="tight")
    plt.show()

plot_distributions(df)


# %% [markdown]
# ## 6. Variables catégorielles

# %% Catégorielles
def plot_categoricals(df: pd.DataFrame) -> None:
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    cat_cols = [c for c in cat_cols if df[c].nunique() <= 20]  # Cardinalité raisonnable

    if not cat_cols:
        print("Aucune colonne catégorielle à faible cardinalité.")
        return

    n_cols = min(3, len(cat_cols))
    n_rows = int(np.ceil(len(cat_cols) / n_cols))
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(15, n_rows * 4))
    axes = np.array(axes).flatten() if hasattr(axes, "__iter__") else [axes]

    for i, col in enumerate(cat_cols):
        ax = axes[i]
        counts = df[col].value_counts()
        colors = sns.color_palette("husl", len(counts))
        bars = ax.bar(range(len(counts)), counts.values, color=colors)
        ax.set_xticks(range(len(counts)))
        ax.set_xticklabels(counts.index, rotation=30, ha="right", fontsize=9)
        ax.set_title(f"{col}\n({df[col].nunique()} modalités)", fontsize=11)
        ax.set_ylabel("Fréquence")

        # Annotations
        for bar, val in zip(bars, counts.values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.5,
                str(val),
                ha="center", va="bottom", fontsize=8,
            )

    for j in range(len(cat_cols), len(axes)):
        axes[j].set_visible(False)

    plt.suptitle("Variables catégorielles", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig("reports/eda_categoricals.png", dpi=150, bbox_inches="tight")
    plt.show()

    print("\nRésumé cardinalités :")
    for col in cat_cols:
        print(f"  {col:<25} {df[col].nunique()} modalités | mode: '{df[col].mode()[0]}'")

plot_categoricals(df)


# %% [markdown]
# ## 7. Matrice de corrélation

# %% Corrélation
def plot_correlation(df: pd.DataFrame) -> None:
    num_df = df.select_dtypes(include=[np.number])
    if num_df.shape[1] < 2:
        print("Pas assez de colonnes numériques pour la corrélation.")
        return

    corr = num_df.corr()
    mask = np.triu(np.ones_like(corr, dtype=bool))  # Triangle supérieur masqué

    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(
        corr,
        mask=mask,
        annot=True,
        fmt=".2f",
        cmap="RdBu_r",
        center=0,
        vmin=-1, vmax=1,
        ax=ax,
        linewidths=0.5,
        cbar_kws={"label": "Pearson r"},
    )
    ax.set_title("Matrice de corrélation (Pearson)", fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig("reports/eda_correlation.png", dpi=150, bbox_inches="tight")
    plt.show()

    # Paires fortement corrélées
    corr_pairs = []
    for i in range(len(corr.columns)):
        for j in range(i + 1, len(corr.columns)):
            val = corr.iloc[i, j]
            if abs(val) > 0.5:
                corr_pairs.append((corr.columns[i], corr.columns[j], round(val, 3)))

    if corr_pairs:
        print("\nPaires fortement corrélées (|r| > 0.5) :")
        for c1, c2, r in sorted(corr_pairs, key=lambda x: abs(x[2]), reverse=True):
            flag = "🔴" if abs(r) > 0.8 else "🟡"
            print(f"  {flag} {c1:<20} ↔ {c2:<20} r = {r:+.3f}")
    else:
        print("\n✅ Aucune corrélation forte détectée (|r| > 0.5).")

plot_correlation(df)


# %% [markdown]
# ## 8. Détection des outliers (boxplots)

# %% Outliers
def plot_outliers(df: pd.DataFrame) -> None:
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if not num_cols:
        return

    fig, axes = plt.subplots(1, len(num_cols), figsize=(max(12, len(num_cols) * 2.5), 5))
    if len(num_cols) == 1:
        axes = [axes]

    for ax, col in zip(axes, num_cols):
        data = df[col].dropna()
        q1, q3 = data.quantile(0.25), data.quantile(0.75)
        iqr = q3 - q1
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        n_outliers = ((data < lower) | (data > upper)).sum()

        bp = ax.boxplot(data, patch_artist=True, notch=True,
                        boxprops=dict(facecolor="#1D9E75", alpha=0.5),
                        medianprops=dict(color="#0F6E56", linewidth=2))
        color = "#dc3545" if n_outliers > len(data) * 0.05 else "#28a745"
        ax.set_title(f"{col}\n{n_outliers} outliers", fontsize=10, color=color)
        ax.set_xlabel("")

    plt.suptitle("Détection des outliers (IQR × 1.5)", fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig("reports/eda_outliers.png", dpi=150, bbox_inches="tight")
    plt.show()

    # Rapport outliers
    print("\nRapport outliers :")
    for col in num_cols:
        data = df[col].dropna()
        q1, q3 = data.quantile(0.25), data.quantile(0.75)
        iqr = q3 - q1
        n_out = ((data < q1 - 1.5*iqr) | (data > q3 + 1.5*iqr)).sum()
        pct = n_out / len(data) * 100
        flag = "❌" if pct > 5 else "⚠️" if pct > 1 else "✅"
        print(f"  {flag} {col:<25} {n_out:3d} outliers ({pct:.1f}%)")

plot_outliers(df)


# %% [markdown]
# ## 9. Résumé et recommandations

# %%
print("\n" + "="*55)
print("  RÉSUMÉ EDA & RECOMMANDATIONS")
print("="*55)

num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
missing_cols = df.columns[df.isnull().any()].tolist()
dup_count = df.duplicated().sum()

print(f"\n📐 Shape              : {df.shape[0]} lignes × {df.shape[1]} colonnes")
print(f"🔢 Colonnes numériques : {len(num_cols)} — {num_cols}")
print(f"🔤 Colonnes texte      : {len(cat_cols)}")
print(f"🕳️  Colonnes manquantes : {len(missing_cols)} — {missing_cols}")
print(f"👥 Doublons            : {dup_count}")

print("\n📋 Actions recommandées pour le pipeline :")
if missing_cols:
    for col in missing_cols:
        rate = df[col].isnull().mean()
        if rate > 0.30:
            print(f"   ❌ Supprimer '{col}' (>{rate*100:.0f}% manquant)")
        elif rate > 0.15:
            print(f"   ⚠️  Imputer '{col}' avec médiane/mode ({rate*100:.0f}% manquant)")
        else:
            print(f"   ✅ '{col}' acceptable ({rate*100:.1f}% manquant)")

phi_candidates = [c for c in df.columns if any(
    k in c.lower() for k in ["name", "id", "email", "phone", "address", "ssn"]
)]
if phi_candidates:
    print(f"   🔒 Anonymiser colonnes PHI : {phi_candidates}")

if dup_count > 0:
    print(f"   🔁 Supprimer {dup_count} doublon(s)")

print("\n✅ EDA terminée — Rapports sauvegardés dans reports/")
print("="*55)
