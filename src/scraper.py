"""
scraper.py
----------
Module de collecte de données médicales via web scraping.
Supporte BeautifulSoup (pages statiques) et Selenium (pages dynamiques).
Gère aussi les fichiers CSV locaux.
"""

import logging
import time
import csv
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

# Selenium est optionnel — utilisé uniquement pour les pages JS
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("scraper")


# ---------------------------------------------------------------------------
# Fonctions utilitaires
# ---------------------------------------------------------------------------

def is_valid_url(url: str) -> bool:
    """Valide si une URL est bien formée."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def is_kaggle_url(url: str) -> bool:
    """Détecte si l'URL est un lien Kaggle (non accessible directement)."""
    return "kaggle.com/datasets" in url.lower()


def is_local_file(path: str) -> bool:
    """Vérifie si le chemin est un fichier local CSV."""
    p = Path(path)
    return p.exists() and p.suffix.lower() == ".csv"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class ScraperConfig:
    """Paramètres de configuration du scraper."""
    url: str
    output_path: str = "data/raw/medical_raw.csv"
    mode: str = "static"             # "static" | "dynamic"
    request_delay: float = 1.5       # secondes entre les requêtes
    timeout: int = 30                # timeout HTTP en secondes
    max_retries: int = 3             # tentatives max par requête
    headless: bool = True            # Selenium headless mode
    headers: dict = field(default_factory=lambda: {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    })


# ---------------------------------------------------------------------------
# Scraper statique (BeautifulSoup + Requests)
# ---------------------------------------------------------------------------

class StaticScraper:
    """Scraper pour pages HTML statiques via requests + BeautifulSoup."""

    def __init__(self, config: ScraperConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(config.headers)

    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Télécharge une page HTML avec gestion des retries."""
        # Validation préalable
        if is_kaggle_url(url):
            err_msg = (
                f"❌ URL Kaggle non supportée en mode HTML statique : {url}\n"
                f"   → Kaggle demande une authentification\n"
                f"   → Solution : utiliser le mode automatique Kaggle ou trouver une URL brute"
            )
            logger.error(err_msg)
            raise ValueError(err_msg)

        if not is_valid_url(url):
            err_msg = f"❌ URL invalide ou malformée : {url}"
            logger.error(err_msg)
            raise ValueError(err_msg)

        last_ex = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                logger.info(f"Requête GET [{attempt}/{self.config.max_retries}] → {url}")
                response = self.session.get(url, timeout=self.config.timeout)
                response.raise_for_status()
                return BeautifulSoup(response.text, "html.parser")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Erreur requête (tentative {attempt}) : {e}")
                last_ex = e
                if attempt < self.config.max_retries:
                    time.sleep(self.config.request_delay * attempt)
        logger.error(f"Impossible de charger : {url}")
        if last_ex:
            raise last_ex
        return None

    def _fetch_raw_text(self, url: str) -> Optional[str]:
        """Télécharge le contenu brut (texte/CSV) d'une URL."""
        last_ex = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                logger.info(f"Requête GET (texte brut) [{attempt}] → {url}")
                response = self.session.get(url, timeout=self.config.timeout)
                response.raise_for_status()
                return response.text
            except requests.exceptions.RequestException as e:
                logger.warning(f"Erreur requête (tentative {attempt}) : {e}")
                last_ex = e
                if attempt < self.config.max_retries:
                    time.sleep(self.config.request_delay * attempt)
        if last_ex:
            raise last_ex
        return None

    def scrape(self) -> pd.DataFrame:
        """
        Scrape la source (HTML page ou fichier brut CSV/texte).
        Auto-détecte le format et applique le parser approprié.
        """
        url = self.config.url
        
        # Cas 1 : URL pointe vers un fichier CSV/data brut (pas HTML)
        if url.lower().endswith(('.csv', '.data', '.txt')):
            logger.info(f"Détecté format fichier brut : {url}")
            text = self._fetch_raw_text(url)
            if text:
                try:
                    # Essayer pandas read_csv sur le texte
                    from io import StringIO
                    df = pd.read_csv(StringIO(text), sep=None, engine='python')
                    if not df.empty:
                        logger.info(f"✅ Fichier brut parsé : {df.shape[0]} lignes × {df.shape[1]} colonnes")
                        return df
                except Exception as e:
                    logger.warning(f"Erreur parsing CSV : {e}")
            return pd.DataFrame()
        
        # Cas 2 : URL pointe vers une page HTML
        soup = self._fetch_page(url)
        if soup is None:
            return pd.DataFrame()

        # Tenter l'extraction depuis un tableau HTML
        tables = soup.find_all("table")
        if tables:
            logger.info(f"{len(tables)} tableau(x) trouvé(s) — extraction du premier")
            try:
                df = pd.read_html(str(tables[0]))[0]
                logger.info(f"✅ Tableau HTML parsé : {df.shape[0]} lignes × {df.shape[1]} colonnes")
                return df
            except Exception as e:
                logger.warning(f"Erreur parsing tableau HTML : {e}")

        # Fallback 1 : Essayer de charger comme CSV si contient un pattern CSV
        try:
            text = soup.get_text()
            # Si le texte contient des lignes séparées, le traiter comme CSV
            if "\n" in text and ("," in text or "\t" in text):
                logger.info("Détecté format texte délimité — tentative parsing CSV")
                from io import StringIO
                df = pd.read_csv(StringIO(text), sep=None, engine='python')
                if not df.empty:
                    logger.info(f"✅ CSV texte parsé : {df.shape[0]} lignes × {df.shape[1]} colonnes")
                    return df
        except Exception as e:
            logger.warning(f"Erreur parsing CSV texte : {e}")

        # Fallback 2 : extraction générique depuis les listes/divs
        logger.warning("Aucun tableau trouvé — extraction générique")
        return self._extract_generic(soup)

    def _extract_generic(self, soup: BeautifulSoup) -> pd.DataFrame:
        """Extraction de données non-tabulaires sous forme de dict."""
        records = []
        for row in soup.find_all("li"):
            text = row.get_text(separator="|", strip=True)
            parts = text.split("|")
            if len(parts) >= 2:
                records.append({"field": parts[0], "value": parts[1]})
        return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Scraper dynamique (Selenium)
# ---------------------------------------------------------------------------

class DynamicScraper:
    """Scraper pour pages JavaScript dynamiques via Selenium."""

    def __init__(self, config: ScraperConfig):
        if not SELENIUM_AVAILABLE:
            raise ImportError(
                "Selenium n'est pas installé. Lancez : pip install selenium"
            )
        self.config = config
        self.driver = self._init_driver()

    def _init_driver(self) -> webdriver.Chrome:
        """Initialise le driver Chrome en mode headless."""
        options = Options()
        if self.config.headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f"user-agent={self.config.headers['User-Agent']}")
        logger.info("Initialisation du driver Chrome (headless)")
        return webdriver.Chrome(options=options)

    def scrape(self) -> pd.DataFrame:
        """Charge la page, attend le rendu JS, puis extrait les données."""
        try:
            logger.info(f"Chargement Selenium : {self.config.url}")
            self.driver.get(self.config.url)

            # Attendre que le tableau soit présent dans le DOM
            WebDriverWait(self.driver, self.config.timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "table"))
            )
            time.sleep(self.config.request_delay)

            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            tables = soup.find_all("table")
            if tables:
                df = pd.read_html(str(tables[0]))[0]
                logger.info(f"Données Selenium extraites : {df.shape[0]} lignes")
                return df
            logger.warning("Aucun tableau trouvé après rendu JS")
            return pd.DataFrame()

        except Exception as e:
            logger.error(f"Erreur Selenium : {e}")
            return pd.DataFrame()
        finally:
            self.driver.quit()


# ---------------------------------------------------------------------------
# Scraper Kaggle (kagglehub)
# ---------------------------------------------------------------------------

class KaggleScraper:
    """Scraper pour télécharger des datasets depuis Kaggle via kagglehub."""

    def __init__(self, config: ScraperConfig):
        self.config = config

    def scrape(self) -> pd.DataFrame:
        """Télécharge le dataset public Kaggle et le charge en DataFrame."""
        url = self.config.url
        logger.info(f"Détection d'un dataset Kaggle : {url}")

        # Regex pour extraire owner/dataset
        import re
        match = re.search(r"kaggle\.com/datasets/([^/]+)/([^/?#\s]+)", url)
        if not match:
            err_msg = f"URL Kaggle invalide ou non supportée : {url}"
            logger.error(err_msg)
            raise ValueError(err_msg)

        owner = match.group(1)
        dataset_name = match.group(2)
        dataset_handle = f"{owner}/{dataset_name}"
        logger.info(f"Identifiant Kaggle extrait : {dataset_handle}")

        try:
            import kagglehub
        except ImportError as e:
            err_msg = "La bibliothèque 'kagglehub' n'est pas installée. Lancez : pip install kagglehub"
            logger.error(err_msg)
            raise ImportError(err_msg) from e

        try:
            logger.info("Téléchargement du dataset avec kagglehub...")
            downloaded_dir = kagglehub.dataset_download(dataset_handle)
            logger.info(f"Téléchargement réussi dans : {downloaded_dir}")

            downloaded_path = Path(downloaded_dir)
            csv_files = list(downloaded_path.glob("**/*.csv"))
            if not csv_files:
                err_msg = f"Aucun fichier CSV trouvé dans le dossier téléchargé : {downloaded_dir}"
                logger.error(err_msg)
                raise FileNotFoundError(err_msg)

            # Prendre le premier CSV trouvé
            csv_file = csv_files[0]
            logger.info(f"Lecture du fichier CSV : {csv_file.name}")
            df = pd.read_csv(csv_file)
            return df

        except Exception as e:
            logger.error(f"Erreur lors du téléchargement Kaggle : {e}")
            raise e


# ---------------------------------------------------------------------------
# Classe principale — point d'entrée public
# ---------------------------------------------------------------------------

class MedicalScraper:
    """
    Orchestrateur du scraping médical.
    Choisit automatiquement entre KaggleScraper, StaticScraper et DynamicScraper.
    """

    def __init__(self, config: ScraperConfig):
        # Normaliser l'URL si ce n'est pas un fichier local et que ça ne commence pas par un protocole
        url = config.url.strip()
        if not is_local_file(url) and not url.lower().startswith(("http://", "https://")):
            url = "https://" + url
            config.url = url

        self.config = config
        if is_kaggle_url(config.url):
            self._scraper = KaggleScraper(config)
        else:
            self._scraper = None

    def run(self) -> pd.DataFrame:
        """Lance le scraping approprié selon la source et sauvegarde les données."""
        url_or_path = self.config.url
        
        # Cas 1 : Fichier CSV local
        if is_local_file(url_or_path):
            logger.info(f"Source locale détectée : {url_or_path}")
            return self._load_local_csv(url_or_path)
        
        # Cas 2 : URL Kaggle
        if is_kaggle_url(url_or_path):
            logger.info("Traitement d'une URL Kaggle via KaggleScraper")
            self._scraper = KaggleScraper(self.config)
            df = self._scraper.scrape()
            if df.empty:
                logger.error("Aucune donnée collectée depuis Kaggle — arrêt du pipeline")
                return df
            self._save(df)
            return df
        
        # Cas 3 : URL HTTP/HTTPS standard
        if not is_valid_url(url_or_path):
            err_msg = f"❌ URL invalide : {url_or_path}"
            logger.error(err_msg)
            raise ValueError(err_msg)
        
        logger.info(f"Démarrage du scraping [{self.config.mode}] : {url_or_path}")
        
        self._scraper = (
            DynamicScraper(self.config)
            if self.config.mode == "dynamic"
            else StaticScraper(self.config)
        )
        
        df = self._scraper.scrape()

        if df.empty:
            logger.error("Aucune donnée collectée — arrêt du pipeline")
            return df

        self._save(df)
        return df

    def _load_local_csv(self, path: str) -> pd.DataFrame:
        """Charge un fichier CSV local."""
        try:
            df = pd.read_csv(path)
            logger.info(f"CSV chargé : {path} ({len(df)} lignes × {len(df.columns)} colonnes)")
            self._save(df)
            return df
        except Exception as e:
            logger.error(f"Erreur chargement CSV {path} : {e}")
            raise e

    def _save(self, df: pd.DataFrame) -> None:
        """Sauvegarde le DataFrame brut en CSV."""
        output = Path(self.config.output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output, index=False, quoting=csv.QUOTE_ALL)
        logger.info(f"Données brutes sauvegardées → {output} ({len(df)} lignes)")


# ---------------------------------------------------------------------------
# Utilisation directe (CLI)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    config = ScraperConfig(
        url="https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/processed.cleveland.data",
        output_path="data/raw/medical_raw.csv",
        mode="static",
    )
    scraper = MedicalScraper(config)
    df = scraper.run()
    print(df.head())