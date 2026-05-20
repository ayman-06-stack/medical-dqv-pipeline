"""
pages/02_quality.py
-------------------
Page Streamlit — Dashboard DQV (Data Quality Verification).
Affiche les résultats des checks qualité avec graphiques Plotly interactifs.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from dqv import DataQualityVerifier, DQVConfig

# ---------------------------------------------------------------------------
# Config page
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Qualité DQV — Medical Pipeline",
    page_icon="✅",
    layout="wide",
)

st.markdown("""
<style>
    .check-card {
        padding: 14px 16px;
        border-radius: 10px;
        margin-bottom: 12px;
        border-left: 5px solid;
    }
    .check-pass { background:#d4edda; border-color:#28a745; }
    .check-warn { background:#fff3cd; border-color:#ffc107; }
    .check-fail { background:#f8d7da; border-color:#dc3545; }
    .check-title { font-weight: 700; font-size: 14px; margin-bottom: 4px; }
    .check-msg   { font-size: 13px; }
    .gate-pass { background:#d4edda; color:#155724; padding:16px 20px;
                 border-radius:10px; font-size:20px; font-weight:700;
                 text-align:center; margin-bottom:20px; }
    .gate-fail { background:#f8d7da; color:#721c24; padding:16px 20px;
                 border-radius:10px; font-size:20px; font-weight:700;
                 text-align:center; margin-bottom:20px; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def _init():
    for k, v in {
        "df_anonymized": None,
        "df_transformed": None,
        "dqv_results": None,
        "gate_passed": None,
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()


# ---------------------------------------------------------------------------
# Helpers — chargement depuis disque
# ---------------------------------------------------------------------------

def _load_df() -> pd.DataFrame:
    """Charge le dataset anonymisé depuis session ou disque."""
    if st.session_state.df_anonymized is not None:
        return st.session_state.df_anonymized
    p = Path("data/processed/medical_v1.0_anonymized.csv")
    if p.exists():
        return pd.read_csv(p)
    return pd.DataFrame()


def _load_dqv_json() -> dict:
    p = Path("reports/dqv_results.json")
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}


# ---------------------------------------------------------------------------
# Composants visuels
# ---------------------------------------------------------------------------

def _render_gate(gate_passed: bool) -> None:
    if gate_passed:
        st.markdown('<div class="gate-pass">✅ Gate DQV : ACCEPTÉ — Dataset prêt pour la transformation</div>',
                    unsafe_allow_html=True)
    else:
        st.markdown('<div class="gate-fail">❌ Gate DQV : REJETÉ — Des problèmes critiques ont été détectés</div>',
                    unsafe_allow_html=True)


def _render_check_cards(results: list) -> None:
    for r in results:
        status = r.get("status", "warn")
        css_class = f"check-{status}"
        icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}.get(status, "?")
        st.markdown(
            f"""<div class="check-card {css_class}">
                  <div class="check-title">{icon} {r.get('name', '')}</div>
                  <div class="check-msg">{r.get('message', '')}</div>
               </div>""",
            unsafe_allow_html=True,
        )


def _chart_missing(df: pd.DataFrame) -> go.Figure:
    """Heatmap des valeurs manquantes par colonne."""
    missing = df.isnull().mean().reset_index()
    missing.columns = ["Colonne", "Taux manquant"]
    missing["Taux %"] = (missing["Taux manquant"] * 100).round(2)
    missing = missing.sort_values("Taux manquant", ascending=False)

    fig = px.bar(
        missing,
        x="Colonne",
        y="Taux %",
        color="Taux %",
        color_continuous_scale=["#28a745", "#ffc107", "#dc3545"],
        range_color=[0, 100],
        title="Taux de valeurs manquantes par colonne (%)",
        text="Taux %",
    )
    fig.add_hline(y=15, line_dash="dash", line_color="red",
                  annotation_text="Seuil 15%", annotation_position="top right")
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(
        height=380,
        coloraxis_showscale=False,
        margin=dict(t=50, b=40, l=20, r=20),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def _chart_distributions(df: pd.DataFrame) -> list:
    """Histogrammes des colonnes numériques."""
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    figs = []
    for col in numeric_cols[:6]:  # Max 6 colonnes
        fig = px.histogram(
            df,
            x=col,
            nbins=30,
            title=f"Distribution : {col}",
            color_discrete_sequence=["#1D9E75"],
        )
        fig.update_layout(
            height=280,
            margin=dict(t=40, b=20, l=20, r=20),
            showlegend=False,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        figs.append((col, fig))
    return figs


def _chart_correlation(df: pd.DataFrame) -> go.Figure:
    """Heatmap de corrélation entre variables numériques."""
    numeric = df.select_dtypes(include=[np.number])
    if numeric.shape[1] < 2:
        return None
    corr = numeric.corr().round(2)
    fig = px.imshow(
        corr,
        color_continuous_scale="RdBu_r",
        zmin=-1, zmax=1,
        title="Matrice de corrélation",
        text_auto=True,
    )
    fig.update_layout(
        height=420,
        margin=dict(t=50, b=20, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def _chart_summary_donut(n_pass: int, n_warn: int, n_fail: int) -> go.Figure:
    """Donut chart récapitulatif des checks."""
    labels = ["Pass ✅", "Warn ⚠️", "Fail ❌"]
    values = [n_pass, n_warn, n_fail]
    colors = ["#28a745", "#ffc107", "#dc3545"]
    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.6,
        marker_colors=colors,
        textinfo="label+value",
        hoverinfo="label+percent",
    ))
    fig.update_layout(
        height=280,
        margin=dict(t=20, b=20, l=20, r=20),
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        annotations=[dict(text=f"{n_pass}/{n_pass+n_warn+n_fail}", x=0.5, y=0.5,
                          font_size=20, showarrow=False, font_color="#1D9E75")],
    )
    return fig


# ---------------------------------------------------------------------------
# UI principale
# ---------------------------------------------------------------------------

st.title("✅ Étape 2 — Dashboard Qualité (DQV)")
st.markdown(
    "Vérification automatique de la qualité du dataset anonymisé. "
    "Les checks s'appuient sur **Great Expectations** et **Pandera**."
)
st.divider()

# Chargement du dataset
df = _load_df()

if df.empty:
    st.warning("⚠️ Aucun dataset disponible. Complétez d'abord l'**Étape 1 : Collecte**.")
    st.stop()

# --- Panneau de config ---
with st.expander("⚙️ Paramètres DQV", expanded=False):
    col1, col2, col3 = st.columns(3)
    with col1:
        missing_thresh = st.slider("Seuil valeurs manquantes (%)", 5, 50, 15, 5) / 100
    with col2:
        drift_thresh = st.slider("Seuil drift distribution", 0.1, 1.0, 0.3, 0.1)
    with col3:
        age_max = st.number_input("Âge maximum autorisé", 100, 150, 120)

run_dqv = st.button("▶️ Lancer les vérifications DQV", type="primary", use_container_width=True)

# --- Exécution DQV ---
if run_dqv:
    with st.spinner("Exécution des checks DQV…"):
        config = DQVConfig(
            missing_threshold=missing_thresh,
            distribution_drift_threshold=drift_thresh,
            age_max=float(age_max),
            report_path="reports/dqv_report.html",
            results_path="reports/dqv_results.json",
        )
        verifier = DataQualityVerifier(config)
        gate_passed, results = verifier.run(df)

        st.session_state.gate_passed = gate_passed
        st.session_state.dqv_results = {
            "gate_passed": gate_passed,
            "summary": {
                "pass": sum(1 for r in results if r.status == "pass"),
                "warn": sum(1 for r in results if r.status == "warn"),
                "fail": sum(1 for r in results if r.status == "fail"),
            },
            "checks": [r.to_dict() for r in results],
        }

# --- Chargement depuis disque si dispo ---
dqv_data = st.session_state.dqv_results or _load_dqv_json()
gate_passed = st.session_state.gate_passed

# --- Résultats ---
if dqv_data:
    st.divider()
    checks = dqv_data.get("checks", [])
    summary = dqv_data.get("summary", {})
    n_pass = summary.get("pass", 0)
    n_warn = summary.get("warn", 0)
    n_fail = summary.get("fail", 0)

    # Gate banner
    _render_gate(dqv_data.get("gate_passed", False))

    # KPIs
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("✅ Checks réussis", n_pass)
    k2.metric("⚠️ Avertissements", n_warn)
    k3.metric("❌ Échecs", n_fail)
    k4.metric("Total checks", n_pass + n_warn + n_fail)

    st.divider()

    # Tabs
    tab_checks, tab_missing, tab_distrib, tab_corr, tab_report = st.tabs([
        "📋 Checks détaillés",
        "🕳️ Valeurs manquantes",
        "📊 Distributions",
        "🔗 Corrélations",
        "📄 Rapport HTML",
    ])

    with tab_checks:
        col_checks, col_donut = st.columns([2, 1])
        with col_checks:
            st.subheader("Résultats des vérifications")
            _render_check_cards(checks)
        with col_donut:
            st.subheader("Résumé")
            st.plotly_chart(
                _chart_summary_donut(n_pass, n_warn, n_fail),
                use_container_width=True,
            )

    with tab_missing:
        st.plotly_chart(_chart_missing(df), use_container_width=True)
        missing_df = df.isnull().sum().rename("Manquants").reset_index()
        missing_df.columns = ["Colonne", "Manquants"]
        missing_df["Taux (%)"] = (missing_df["Manquants"] / len(df) * 100).round(2)
        missing_df["Statut"] = missing_df["Taux (%)"].apply(
            lambda x: "✅ OK" if x <= 15 else ("⚠️ Warn" if x <= 30 else "❌ Fail")
        )
        st.dataframe(missing_df, use_container_width=True, hide_index=True)

    with tab_distrib:
        figs = _chart_distributions(df)
        if figs:
            cols = st.columns(2)
            for i, (col_name, fig) in enumerate(figs):
                with cols[i % 2]:
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Aucune colonne numérique trouvée pour les distributions.")

    with tab_corr:
        corr_fig = _chart_correlation(df)
        if corr_fig:
            st.plotly_chart(corr_fig, use_container_width=True)
        else:
            st.info("Au moins 2 colonnes numériques sont nécessaires.")

    with tab_report:
        report_path = Path("reports/dqv_report.html")
        if report_path.exists():
            with open(report_path, encoding="utf-8") as f:
                html_content = f.read()
            st.components.v1.html(html_content, height=600, scrolling=True)
            with open(report_path, "rb") as f:
                st.download_button(
                    "⬇️ Télécharger le rapport HTML",
                    data=f,
                    file_name="dqv_report.html",
                    mime="text/html",
                )
        else:
            st.info("Lancez les vérifications DQV pour générer le rapport HTML.")

else:
    st.info("👆 Cliquez sur **Lancer les vérifications DQV** pour démarrer.")

# Navigation
st.divider()
if gate_passed:
    st.success("✅ Gate DQV passé — Continuez sur **Étape 3 : Output** pour transformer et exporter.")
elif gate_passed is False:
    st.error("❌ Gate DQV rejeté — Retournez à l'**Étape 1** pour corriger la source de données.")