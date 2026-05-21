"""
pages/01_collect.py
-------------------
Page Streamlit — Collecte & Anonymisation des données médicales.
Permet de saisir une URL source, lancer le scraping et l'anonymisation.
"""

import logging
import sys
import time
from pathlib import Path

import pandas as pd
import streamlit as st

# Ajouter src/ au path pour les imports
sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from scraper import MedicalScraper, ScraperConfig
from anonymizer import MedicalAnonymizer


class StreamlitLogHandler(logging.Handler):
    """Custom logging handler to redirect package logs to Streamlit session state logs."""
    def __init__(self):
        super().__init__()
        self.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))

    def emit(self, record):
        try:
            msg = self.format(record)
            if "collect_logs" in st.session_state:
                st.session_state.collect_logs.append(msg)
        except Exception:
            self.handleError(record)


@st.cache_resource
def setup_streamlit_logging():
    handler = StreamlitLogHandler()
    for logger_name in ["scraper", "pipeline", "anonymizer"]:
        l = logging.getLogger(logger_name)
        l.setLevel(logging.INFO)
        l.addHandler(handler)

# ---------------------------------------------------------------------------
# Config page
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Collecte — Medical DQV",
    page_icon="🔌",
    layout="wide",
)

st.markdown("""
<style>
    .step-card {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 16px 20px;
        border-left: 4px solid #1D9E75;
        margin-bottom: 16px;
    }
    .step-title { font-weight: 700; font-size: 15px; color: #1D9E75; margin-bottom: 4px; }
    .step-desc  { font-size: 13px; color: #555; }
    .log-box {
        background: #0d1117;
        color: #58d68d;
        font-family: monospace;
        font-size: 12px;
        padding: 14px;
        border-radius: 8px;
        max-height: 260px;
        overflow-y: auto;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def _init():
    for k, v in {
        "df_raw": None,
        "df_anonymized": None,
        "collect_logs": [],
        "pipeline_ran": False,
        "source_url": "",
        "anon_report": None,
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()
setup_streamlit_logging()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    st.session_state.collect_logs.append(f"[{ts}] {msg}")


def _render_logs() -> None:
    if st.session_state.collect_logs:
        logs_html = "<br>".join(st.session_state.collect_logs[-40:])
        st.markdown(f'<div class="log-box">{logs_html}</div>', unsafe_allow_html=True)


def _df_preview(df: pd.DataFrame, title: str, max_rows: int = 5) -> None:
    st.markdown(f"**{title}** — `{df.shape[0]}` lignes × `{df.shape[1]}` colonnes")
    st.dataframe(df.head(max_rows), use_container_width=True)


# ---------------------------------------------------------------------------
# Exemples de datasets médicaux publics
# ---------------------------------------------------------------------------

SAMPLE_DATASETS = {
    "Heart Disease (UCI)": (
        "https://archive.ics.uci.edu/ml/machine-learning-databases/"
        "heart-disease/processed.cleveland.data",
        "static",
    ),
    "Diabetes (Kaggle CSV Direct)": (
        "https://raw.githubusercontent.com/jbrownlee/Datasets/master/pima-indians-diabetes.data.csv",
        "static",
    ),
    "Breast Cancer (UCI)": (
        "https://archive.ics.uci.edu/ml/machine-learning-databases/"
        "breast-cancer/breast-cancer.data",
        "static",
    ),
    "Healthcare Data (GitHub CSV)": (
        "https://raw.githubusercontent.com/stedy/Healthcare-Data/main/healthcare_data.csv",
        "static",
    ),
    "📁 Fichier CSV local…": ("", "static"),
}


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

st.title("🔌 Étape 1 — Collecte & Anonymisation")
st.markdown(
    "Saisissez l'URL d'une source de données médicales publique, "
    "un chemin local vers un fichier CSV, configurez les paramètres et lancez le pipeline."
)

# 📌 Info Kaggle
st.info("""
**💡 Support automatique de Kaggle :** Vous pouvez simplement coller l'URL d'un dataset Kaggle public (ex: `kaggle.com/datasets/prasad22/healthcare-dataset`) dans le champ ci-dessous. Le scraper le téléchargera automatiquement !
""")

st.divider()

# --- Sélection de la source ---
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("Source de données")

    preset = st.selectbox(
        "Dataset prédéfini",
        options=list(SAMPLE_DATASETS.keys()),
        index=0,
    )
    preset_url, preset_mode = SAMPLE_DATASETS[preset]

    url_input = st.text_input(
        "URL source ou chemin CSV local",
        value=preset_url,
        placeholder="https://... ou C:/path/to/file.csv",
        help="Lien direct vers un CSV/HTTP ou chemin local (ex: data/raw/mydata.csv)",
    )
    st.session_state.source_url = url_input

with col_right:
    st.subheader("Paramètres scraper")
    scraper_mode = st.radio(
        "Mode scraping",
        ["static", "dynamic"],
        index=0 if preset_mode == "static" else 1,
        help="Static = BeautifulSoup / Dynamic = Selenium (pages JS)",
    )
    request_delay = st.slider("Délai entre requêtes (s)", 0.5, 5.0, 1.5, 0.5)
    max_retries = st.number_input("Tentatives max", 1, 5, 3)

st.divider()

# --- Paramètres anonymisation ---
st.subheader("⚙️ Paramètres d'anonymisation")

col_a, col_b, col_c = st.columns(3)
with col_a:
    k_value = st.number_input(
        "Valeur k (k-anonymity)",
        min_value=2, max_value=10, value=3,
        help="Chaque combinaison de quasi-identifiants apparaît au moins k fois.",
    )
with col_b:
    phi_strategy = st.selectbox(
        "Stratégie PHI directe",
        ["replace", "hash", "drop"],
        help="replace = données synthétiques (Faker) | hash = HMAC | drop = suppression",
    )
with col_c:
    output_name = st.text_input(
        "Nom du fichier de sortie",
        value="medical_v1.0_anonymized.csv",
        help="Nom du CSV anonymisé dans data/processed/",
    )

st.divider()

# --- Bouton de lancement ---
col_btn, col_clear = st.columns([3, 1])
with col_btn:
    run_btn = st.button(
        "🚀 Lancer Collecte + Anonymisation",
        type="primary",
        disabled=not url_input,
        use_container_width=True,
    )
with col_clear:
    if st.button("🗑️ Effacer logs", use_container_width=True):
        st.session_state.collect_logs = []
        st.rerun()

# --- Exécution ---
if run_btn and url_input:
    st.session_state.collect_logs = []
    progress = st.progress(0, text="Initialisation…")

    # ÉTAPE 1 : Scraping
    with st.spinner("Scraping en cours…"):
        _log(f"Démarrage scraping [{scraper_mode}] : {url_input}")
        progress.progress(10, text="Scraping de la source…")

        try:
            config = ScraperConfig(
                url=url_input,
                output_path=f"data/raw/medical_raw.csv",
                mode=scraper_mode,
                request_delay=request_delay,
                max_retries=int(max_retries),
            )
            scraper = MedicalScraper(config)
            df_raw = scraper.run()

            if df_raw.empty:
                st.error(
                    "❌ **Scraping échoué — Aucune donnée collectée.**\n\n"
                    "Causes possibles :\n"
                    "• URL invalide ou inaccessible\n"
                    "• URL Kaggle (nécessite authentification)\n"
                    "• Chemin local inexistant\n"
                    "• Serveur indisponible ou timeout\n"
                    "• Format non reconnu (CSV/HTML)\n\n"
                    "→ Vérifiez l'URL/chemin et réessayez."
                )
                _log("ERREUR : aucune donnée collectée")
                st.stop()

            st.session_state.df_raw = df_raw
            _log(f"✅ Scraping OK — {len(df_raw)} lignes × {len(df_raw.columns)} colonnes")
            progress.progress(40, text="Scraping terminé…")

        except Exception as e:
            st.error(f"❌ **Erreur scraping** : {str(e)}")
            _log(f"ERREUR scraping : {e}")
            st.stop()

    # ÉTAPE 2 : Anonymisation
    with st.spinner("Anonymisation PHI en cours…"):
        _log(f"Anonymisation — k={k_value}, stratégie={phi_strategy}")
        progress.progress(55, text="Anonymisation des données…")

        try:
            anon_output = f"data/processed/{output_name}"
            anonymizer = MedicalAnonymizer(
                k=int(k_value),
                strategy=phi_strategy,
                output_path=anon_output,
                report_path="reports/anonymization_report.json",
            )
            df_anon = anonymizer.run(df_raw)

            if df_anon.empty:
                st.warning("⚠️ Dataset vide après anonymisation — k trop élevé ?")
                _log("AVERTISSEMENT : dataset vide post-anonymisation")
            else:
                st.session_state.df_anonymized = df_anon
                _log(f"✅ Anonymisation OK — {len(df_anon)} lignes conservées")
                rows_dropped = len(df_raw) - len(df_anon)
                if rows_dropped > 0:
                    _log(f"INFO : {rows_dropped} lignes supprimées par k-anonymity")

            st.session_state.pipeline_ran = True
            progress.progress(100, text="Terminé ✅")
            _log("Pipeline collecte + anonymisation terminé avec succès")

        except Exception as e:
            st.error(f"❌ Erreur anonymisation : {e}")
            _log(f"ERREUR anonymisation : {e}")
            st.stop()

# ---------------------------------------------------------------------------
# Résultats
# ---------------------------------------------------------------------------

st.divider()
st.subheader("📋 Logs d'exécution")
_render_logs()

if st.session_state.df_raw is not None or st.session_state.df_anonymized is not None:
    st.divider()
    st.subheader("📊 Aperçu des données")

    tab1, tab2, tab3 = st.tabs(["Données brutes", "Données anonymisées", "Comparaison"])

    with tab1:
        if st.session_state.df_raw is not None:
            _df_preview(st.session_state.df_raw, "Dataset brut (raw)")
            st.markdown("**Statistiques descriptives**")
            st.dataframe(
                st.session_state.df_raw.describe(include="all").T,
                use_container_width=True,
            )
        else:
            st.info("Aucune donnée brute disponible.")

    with tab2:
        if st.session_state.df_anonymized is not None:
            _df_preview(st.session_state.df_anonymized, "Dataset anonymisé")
            st.markdown("**Valeurs manquantes par colonne**")
            missing = st.session_state.df_anonymized.isnull().mean().rename("taux_manquant")
            st.bar_chart(missing)
        else:
            st.info("Aucune donnée anonymisée disponible.")

    with tab3:
        df_r = st.session_state.df_raw
        df_a = st.session_state.df_anonymized
        if df_r is not None and df_a is not None:
            c1, c2, c3 = st.columns(3)
            c1.metric("Lignes brutes", len(df_r))
            c2.metric(
                "Lignes anonymisées",
                len(df_a),
                delta=f"-{len(df_r)-len(df_a)}",
                delta_color="inverse",
            )
            c3.metric(
                "Taux de rétention",
                f"{len(df_a)/len(df_r)*100:.1f}%",
            )

            st.markdown("**Colonnes supprimées (PHI directs)**")
            removed = set(df_r.columns) - set(df_a.columns)
            if removed:
                st.error(f"Colonnes supprimées : `{', '.join(removed)}`")
            else:
                st.success("Aucune colonne supprimée (remplacement synthétique appliqué)")
        else:
            st.info("Lancez le pipeline pour voir la comparaison.")

# --- Navigation vers l'étape suivante ---
st.divider()
if st.session_state.df_anonymized is not None:
    st.success("✅ Étape 1 complète — Rendez-vous sur **Étape 2 : Quality** pour vérifier la qualité.")