"""
scraper.py
----------
Module de collecte de données médicales via web scraping.
Supporte BeautifulSoup (pages statiques) et Selenium (pages dynamiques).
"""

import logging
import time
import csv
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

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
        for attempt in range(1, self.config.max_retries + 1):
            try:
                logger.info(f"Requête GET [{attempt}/{self.config.max_retries}] → {url}")
                response = self.session.get(url, timeout=self.config.timeout)
                response.raise_for_status()
                return BeautifulSoup(response.text, "html.parser")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Erreur requête (tentative {attempt}) : {e}")
                if attempt < self.config.max_retries:
                    time.sleep(self.config.request_delay * attempt)
        logger.error(f"Impossible de charger : {url}")
        return None

    def scrape(self) -> pd.DataFrame:
        """
        Scrape la page et extrait les données tabulaires médicales.
        Cherche en priorité les balises <table>, sinon extrait les listes.
        """
        soup = self._fetch_page(self.config.url)
        if soup is None:
            return pd.DataFrame()

        # Tenter l'extraction depuis un tableau HTML
        tables = soup.find_all("table")
        if tables:
            logger.info(f"{len(tables)} tableau(x) trouvé(s) — extraction du premier")
            df = pd.read_html(str(tables[0]))[0]
            logger.info(f"Données extraites : {df.shape[0]} lignes × {df.shape[1]} colonnes")
            return df

        # Fallback : extraction générique depuis les listes/divs
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
# Classe principale — point d'entrée public
# ---------------------------------------------------------------------------

class MedicalScraper:
    """
    Orchestrateur du scraping médical.
    Choisit automatiquement entre StaticScraper et DynamicScraper
    selon le mode défini dans ScraperConfig.
    """

    def __init__(self, config: ScraperConfig):
        self.config = config
        self._scraper = (
            DynamicScraper(config)
            if config.mode == "dynamic"
            else StaticScraper(config)
        )

    def run(self) -> pd.DataFrame:
        """Lance le scraping et sauvegarde les données brutes."""
        logger.info(f"Démarrage du scraping [{self.config.mode}] : {self.config.url}")
        df = self._scraper.scrape()

        if df.empty:
            logger.error("Aucune donnée collectée — arrêt du pipeline")
            return df

        self._save(df)
        return df

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