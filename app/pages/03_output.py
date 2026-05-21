"""
pages/03_output.py
------------------
Page Streamlit — Transformation, Export CSV & Versioning DVC.
Preview du dataset final, téléchargement et gestion des versions.
"""

import json
import sys
from datetime import datetime
from io import StringIO
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from transformer import MedicalTransformer
from dvc_manager import DVCManager, DVCError

# ---------------------------------------------------------------------------
# Config page
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Output — Medical DQV",
    page_icon="📦",
    layout="wide",
)

st.markdown("""
<style>
    .version-card {
        background: #f0faf6;
        border: 1.5px solid #1D9E75;
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 10px;
    }
    .version-tag  { font-family: monospace; font-weight: 700;
                    color: #0F6E56; font-size: 15px; }
    .version-meta { font-size: 12px; color: #666; margin-top: 4px; }
    .stat-box {
        background: #f8f9fa;
        border-radius: 8px;
        padding: 12px 16px;
        text-align: center;
        border: 1px solid #e9ecef;
    }
    .stat-val   { font-size: 24px; font-weight: 700; color: #1D9E75; }
    .stat-label { font-size: 12px; color: #888; margin-top: 2px; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def _init():
    for k, v in {
        "df_anonymized": None,
        "df_transformed": None,
        "gate_passed": None,
        "version_tag": None,
        "dvc_versions": [],
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_df(path: str) -> pd.DataFrame:
    """Charge un DataFrame depuis session ou disque."""
    p = Path(path)
    if p.exists():
        return pd.read_csv(p)
    return pd.DataFrame()


def _load_anon_report() -> dict:
    p = Path("reports/anonymization_report.json")
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _load_dqv_results() -> dict:
    p = Path("reports/dqv_results.json")
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


def _render_stat(val, label: str) -> str:
    return f"""<div class="stat-box">
        <div class="stat-val">{val}</div>
        <div class="stat-label">{label}</div>
    </div>"""


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

st.title("📦 Étape 3 — Transformation, Export & Versioning DVC")
st.markdown(
    "Appliquez la transformation finale sur le dataset anonymisé, "
    "exportez le CSV nettoyé et créez une version DVC reproductible."
)
st.divider()

# --- Chargement des données ---
df_anon = st.session_state.df_anonymized if st.session_state.df_anonymized is not None else _load_df("data/processed/medical_v1.0_anonymized.csv")
df_trans = st.session_state.df_transformed if st.session_state.df_transformed is not None else _load_df("data/processed/medical_v1.0_transformed.csv")
gate_ok = st.session_state.gate_passed
dqv_data = _load_dqv_results()
anon_report = _load_anon_report()

if df_anon.empty:
    st.warning("⚠️ Aucun dataset anonymisé disponible. Complétez d'abord les **Étapes 1 & 2**.")
    st.stop()

if gate_ok is False and dqv_data:
    st.error("❌ Gate DQV rejeté — La transformation est bloquée. Corrigez les problèmes qualité.")
    st.stop()

# ---------------------------------------------------------------------------
# SECTION 1 — Transformation
# ---------------------------------------------------------------------------

st.subheader("🔄 Transformation des données")

with st.expander("⚙️ Paramètres de transformation", expanded=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        scaler = st.selectbox(
            "Méthode de normalisation",
            ["standard", "minmax"],
            help="standard = Z-score (mean=0, std=1) | minmax = [0, 1]",
        )
    with col2:
        outlier_factor = st.slider(
            "Facteur IQR (outliers)", 1.0, 3.0, 1.5, 0.5,
            help="1.5 = standard | 3.0 = seulement les outliers extrêmes",
        )
    with col3:
        max_ohe = st.number_input(
            "Cardinalité max OHE", 2, 20, 5,
            help="Colonnes catégorielles avec ≤ N modalités → One-Hot Encoding",
        )

run_transform = st.button(
    "⚙️ Lancer la transformation",
    type="primary",
    use_container_width=True,
    disabled=df_anon.empty,
)

if run_transform:
    with st.spinner("Transformation en cours…"):
        try:
            transformer = MedicalTransformer(
                outlier_factor=outlier_factor,
                scaler_method=scaler,
                max_ohe_cardinality=int(max_ohe),
                pipeline_path="data/processed/transformer_pipeline.pkl",
            )
            df_transformed = transformer.fit_transform(df_anon.copy())

            # Sauvegarde
            out_path = Path("data/processed/medical_v1.0_transformed.csv")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            df_transformed.to_csv(out_path, index=False)

            st.session_state.df_transformed = df_transformed
            df_trans = df_transformed
            st.success(f"✅ Transformation OK — {df_transformed.shape[0]} lignes × {df_transformed.shape[1]} colonnes")

        except Exception as e:
            st.error(f"❌ Erreur transformation : {e}")

st.divider()

# ---------------------------------------------------------------------------
# SECTION 2 — Preview dataset final
# ---------------------------------------------------------------------------

st.subheader("📊 Preview du dataset final")

df_display = df_trans if not df_trans.empty else df_anon
dataset_label = "Transformé ✅" if not df_trans.empty else "Anonymisé (non transformé)"

# Stats rapides
s1, s2, s3, s4 = st.columns(4)
with s1:
    st.markdown(_render_stat(df_display.shape[0], "Lignes"), unsafe_allow_html=True)
with s2:
    st.markdown(_render_stat(df_display.shape[1], "Colonnes"), unsafe_allow_html=True)
with s3:
    missing_pct = f"{df_display.isnull().mean().mean()*100:.1f}%"
    st.markdown(_render_stat(missing_pct, "Manquants (moy.)"), unsafe_allow_html=True)
with s4:
    mem = f"{df_display.memory_usage(deep=True).sum() / 1024:.1f} KB"
    st.markdown(_render_stat(mem, "Taille mémoire"), unsafe_allow_html=True)

st.markdown(f"**Dataset affiché : {dataset_label}**")

# Filtres
col_filter, col_search = st.columns([1, 2])
with col_filter:
    selected_cols = st.multiselect(
        "Colonnes à afficher",
        options=df_display.columns.tolist(),
        default=df_display.columns.tolist()[:10],
    )
with col_search:
    n_rows = st.slider("Nombre de lignes à afficher", 5, 100, 20)

df_preview = df_display[selected_cols].head(n_rows) if selected_cols else df_display.head(n_rows)
st.dataframe(df_preview, use_container_width=True, height=320)

# Graphiques explorateurs
with st.expander("📈 Visualisation rapide", expanded=False):
    num_cols = df_display.select_dtypes(include="number").columns.tolist()
    if len(num_cols) >= 2:
        vz1, vz2 = st.columns(2)
        with vz1:
            x_col = st.selectbox("Axe X", num_cols, index=0)
        with vz2:
            y_col = st.selectbox("Axe Y", num_cols, index=min(1, len(num_cols)-1))
        fig = px.scatter(
            df_display, x=x_col, y=y_col,
            title=f"Scatter : {x_col} vs {y_col}",
            color_discrete_sequence=["#1D9E75"],
        )
        fig.update_layout(
            height=350,
            margin=dict(t=40, b=20, l=20, r=20),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Pas assez de colonnes numériques pour le scatter plot.")

st.divider()

# ---------------------------------------------------------------------------
# SECTION 3 — Export CSV
# ---------------------------------------------------------------------------

st.subheader("⬇️ Téléchargement du dataset")

col_dl1, col_dl2 = st.columns(2)

with col_dl1:
    # Dataset final transformé
    csv_final = _df_to_csv_bytes(df_display)
    filename_final = f"medical_clean_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    st.download_button(
        label=f"⬇️ Télécharger le dataset final ({dataset_label})",
        data=csv_final,
        file_name=filename_final,
        mime="text/csv",
        use_container_width=True,
        type="primary",
    )

with col_dl2:
    # Rapport d'anonymisation JSON
    if anon_report:
        anon_json = json.dumps(anon_report, indent=2, ensure_ascii=False, default=str)
        st.download_button(
            label="⬇️ Télécharger rapport anonymisation (JSON)",
            data=anon_json.encode("utf-8"),
            file_name="anonymization_report.json",
            mime="application/json",
            use_container_width=True,
        )
    else:
        st.button("Rapport anonymisation indisponible", disabled=True, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# SECTION 4 — Versioning DVC
# ---------------------------------------------------------------------------

st.subheader("🔁 Versioning DVC")

col_dvc1, col_dvc2 = st.columns([2, 1])

with col_dvc1:
    version_tag = st.text_input(
        "Tag de version",
        value=f"v1.0-anonymized-{datetime.now().strftime('%Y%m%d')}",
        placeholder="ex: v1.0-anonymized-20240615",
        help="Ce tag sera utilisé pour identifier cette version dans DVC + Git.",
    )
    push_remote = st.checkbox(
        "Pousser vers le remote DVC",
        value=False,
        help="Nécessite un remote configuré (Google Drive, S3, GCS...)",
    )

with col_dvc2:
    st.markdown("**Statut DVC**")
    try:
        dvc = DVCManager(repo_path=".")
        dvc_init = dvc.is_initialized()
        versions = dvc.list_versions() if dvc_init else []
        st.success("DVC initialisé ✅") if dvc_init else st.warning("DVC non initialisé ⚠️")
        st.markdown(f"Versions existantes : `{len(versions)}`")
    except Exception:
        dvc_init = False
        versions = []
        st.warning("DVC non détecté")

run_dvc = st.button(
    "🔖 Créer la version DVC",
    type="primary",
    use_container_width=True,
    disabled=not dvc_init or df_display.empty,
)

if run_dvc:
    with st.spinner(f"Versioning DVC → {version_tag}…"):
        try:
            dvc = DVCManager(repo_path=".")
            result_tag = dvc.version_dataset(
                dataset_path="data/processed/medical_v1.0_anonymized.csv",
                version_tag=version_tag,
                push=push_remote,
            )
            st.session_state.version_tag = result_tag
            st.session_state.dvc_versions = dvc.list_versions()
            st.success(f"✅ Version créée : `{result_tag}`")
        except DVCError as e:
            st.error(f"❌ Erreur DVC : {e}")
        except Exception as e:
            st.warning(f"⚠️ DVC ignoré (Git non configuré ?) : {e}")
            st.session_state.version_tag = version_tag

# --- Historique des versions ---
if versions or st.session_state.dvc_versions:
    st.markdown("**Historique des versions**")
    all_versions = list(set(versions + st.session_state.dvc_versions))
    for v in sorted(all_versions, reverse=True):
        is_current = v == st.session_state.version_tag
        badge = " 🟢 **Actuelle**" if is_current else ""
        st.markdown(
            f"""<div class="version-card">
                  <span class="version-tag">{v}</span>{badge}
                  <div class="version-meta">Tag DVC · Dataset médical anonymisé</div>
               </div>""",
            unsafe_allow_html=True,
        )

st.divider()

# ---------------------------------------------------------------------------
# SECTION 5 — Résumé du pipeline
# ---------------------------------------------------------------------------

st.subheader("📋 Résumé complet du pipeline")

col_sum1, col_sum2 = st.columns(2)

with col_sum1:
    st.markdown("**Rapport d'anonymisation**")
    if anon_report:
        st.json(anon_report)
    else:
        st.info("Aucun rapport disponible — lancez l'étape 1.")

with col_sum2:
    st.markdown("**Résultats DQV**")
    if dqv_data:
        summary = dqv_data.get("summary", {})
        st.metric("Checks réussis", f"{summary.get('pass',0)}/{sum(summary.values())}")
        st.metric("Avertissements", summary.get("warn", 0))
        st.metric("Échecs", summary.get("fail", 0))
        gate = dqv_data.get("gate_passed", False)
        st.success("Gate : ACCEPTÉ ✅") if gate else st.error("Gate : REJETÉ ❌")
    else:
        st.info("Aucun résultat DQV disponible — lancez l'étape 2.")

# Statut final
st.divider()
if st.session_state.version_tag:
    st.success(
        f"🎉 Pipeline complet ! Dataset versionné : `{st.session_state.version_tag}` "
        f"— prêt pour la modélisation ML."
    )
else:
    st.info("📌 Créez une version DVC pour finaliser le pipeline.")