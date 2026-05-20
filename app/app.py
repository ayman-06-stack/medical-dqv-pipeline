"""
app.py
------
Application Streamlit principale — Medical DQV Pipeline Dashboard.
Interface multi-pages : collecte, qualité, output.
"""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Configuration globale de la page
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Medical DQV Pipeline",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# CSS personnalisé
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    /* Sidebar header */
    .sidebar-title {
        font-size: 18px;
        font-weight: 700;
        color: #1D9E75;
        margin-bottom: 4px;
    }
    .sidebar-sub {
        font-size: 12px;
        color: #888;
        margin-bottom: 20px;
    }
    /* Metric cards */
    [data-testid="metric-container"] {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 12px 16px;
        border: 1px solid #e9ecef;
    }
    /* Status badge helper */
    .badge-pass { background:#d4edda; color:#155724; padding:3px 10px;
                  border-radius:4px; font-size:12px; font-weight:600; }
    .badge-warn { background:#fff3cd; color:#856404; padding:3px 10px;
                  border-radius:4px; font-size:12px; font-weight:600; }
    .badge-fail { background:#f8d7da; color:#721c24; padding:3px 10px;
                  border-radius:4px; font-size:12px; font-weight:600; }
    /* Section divider */
    .section-divider {
        border-top: 1px solid #e9ecef;
        margin: 24px 0 16px 0;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# État de session — partagé entre toutes les pages
# ---------------------------------------------------------------------------

def init_session_state() -> None:
    """Initialise les variables de session si absentes."""
    defaults = {
        "df_raw": None,
        "df_anonymized": None,
        "df_transformed": None,
        "dqv_results": None,
        "gate_passed": None,
        "version_tag": None,
        "pipeline_ran": False,
        "source_url": "",
        "anon_report": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


init_session_state()


# ---------------------------------------------------------------------------
# Helpers — chargement des rapports existants
# ---------------------------------------------------------------------------

def load_dqv_results(path: str = "reports/dqv_results.json") -> dict:
    """Charge les résultats DQV depuis le JSON si disponible."""
    p = Path(path)
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_anon_report(path: str = "reports/anonymization_report.json") -> dict:
    """Charge le rapport d'anonymisation depuis le JSON si disponible."""
    p = Path(path)
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_dataset(path: str) -> pd.DataFrame:
    """Charge un dataset CSV si le fichier existe."""
    p = Path(path)
    if p.exists():
        return pd.read_csv(p)
    return pd.DataFrame()


# ---------------------------------------------------------------------------
# Sidebar — navigation et statut global
# ---------------------------------------------------------------------------

def render_sidebar() -> None:
    with st.sidebar:
        st.markdown('<div class="sidebar-title">🏥 Medical DQV Pipeline</div>', unsafe_allow_html=True)
        st.markdown('<div class="sidebar-sub">Nettoyage · Anonymisation · Qualité</div>', unsafe_allow_html=True)

        st.divider()

        # Statut du pipeline
        st.markdown("**Statut du pipeline**")
        steps = {
            "Collecte": st.session_state.df_raw is not None,
            "Anonymisation": st.session_state.df_anonymized is not None,
            "DQV": st.session_state.dqv_results is not None,
            "Transformation": st.session_state.df_transformed is not None,
            "Versioning": st.session_state.version_tag is not None,
        }
        for step, done in steps.items():
            icon = "✅" if done else "⬜"
            st.markdown(f"{icon} {step}")

        st.divider()

        # Gate check
        if st.session_state.gate_passed is not None:
            if st.session_state.gate_passed:
                st.success("Gate DQV : **ACCEPTÉ** ✅")
            else:
                st.error("Gate DQV : **REJETÉ** ❌")

        # Version DVC
        if st.session_state.version_tag:
            st.info(f"Version DVC : `{st.session_state.version_tag}`")

        st.divider()
        st.caption("Projet Data Science — Module IA Médicale")


# ---------------------------------------------------------------------------
# Page principale (accueil)
# ---------------------------------------------------------------------------

def render_home() -> None:
    st.title("🏥 Medical Data Cleaning & DQV Pipeline")
    st.markdown(
        "Bienvenue dans le dashboard de nettoyage et vérification qualité "
        "de données médicales. Utilisez les pages dans la sidebar pour naviguer."
    )

    st.divider()

    # KPIs globaux
    col1, col2, col3, col4 = st.columns(4)

    df_raw = st.session_state.df_raw
    df_anon = st.session_state.df_anonymized
    df_final = st.session_state.df_transformed
    dqv = load_dqv_results()

    with col1:
        st.metric(
            "Lignes brutes",
            value=len(df_raw) if df_raw is not None else "—",
        )
    with col2:
        st.metric(
            "Lignes anonymisées",
            value=len(df_anon) if df_anon is not None else "—",
            delta=(
                f"-{len(df_raw) - len(df_anon)} supprimées"
                if df_raw is not None and df_anon is not None
                else None
            ),
        )
    with col3:
        if dqv:
            n_pass = dqv.get("summary", {}).get("pass", 0)
            n_total = sum(dqv.get("summary", {}).values())
            st.metric("Checks DQV réussis", f"{n_pass}/{n_total}")
        else:
            st.metric("Checks DQV réussis", "—")
    with col4:
        st.metric(
            "Colonnes finales",
            value=len(df_final.columns) if df_final is not None else "—",
        )

    st.divider()

    # Architecture du pipeline
    st.subheader("Architecture du pipeline")
    st.markdown("""
    ```
    URL Source → [Scraper] → data/raw/
               → [Anonymizer] → PHI removal + k-anonymity
               → [DQV] → Quality checks + Gate
               → [Transformer] → Encoding + Scaling
               → [DVC] → Versioned dataset v1.0-anonymized
               → [Streamlit] → Preview + Export CSV
    ```
    """)

    # Charger les données existantes si disponibles
    if not st.session_state.pipeline_ran:
        df_anon_disk = load_dataset("data/processed/medical_v1.0_anonymized.csv")
        df_trans_disk = load_dataset("data/processed/medical_v1.0_transformed.csv")
        dqv_disk = load_dqv_results()
        anon_disk = load_anon_report()

        if not df_anon_disk.empty:
            st.session_state.df_anonymized = df_anon_disk
        if not df_trans_disk.empty:
            st.session_state.df_transformed = df_trans_disk
        if dqv_disk:
            st.session_state.dqv_results = dqv_disk
            st.session_state.gate_passed = dqv_disk.get("gate_passed")
        if anon_disk:
            st.session_state.anon_report = anon_disk

    if not st.session_state.pipeline_ran and st.session_state.df_anonymized is None:
        st.info("👉 Allez sur la page **Collecte** pour démarrer le pipeline.")


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

render_sidebar()
render_home()