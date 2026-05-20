"""
dvc_manager.py
--------------
Module de gestion du versioning DVC (Data Version Control).
Interface Python sur les opérations DVC du pipeline.
"""

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("dvc_manager")


# ---------------------------------------------------------------------------
# Exceptions personnalisées
# ---------------------------------------------------------------------------

class DVCError(Exception):
    """Erreur levée lors d'un échec de commande DVC."""
    pass


class DVCNotInitializedError(DVCError):
    """DVC n'est pas initialisé dans ce répertoire."""
    pass


# ---------------------------------------------------------------------------
# Runner de commandes shell
# ---------------------------------------------------------------------------

def _run(cmd: list, cwd: Optional[str] = None, check: bool = True) -> subprocess.CompletedProcess:
    """
    Exécute une commande shell et retourne le résultat.
    Lève DVCError si la commande échoue et check=True.
    """
    cmd_str = " ".join(cmd)
    logger.info(f"$ {cmd_str}")
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        logger.debug(f"stdout: {result.stdout.strip()}")
    if result.returncode != 0:
        logger.error(f"Erreur commande [{result.returncode}] : {result.stderr.strip()}")
        if check:
            raise DVCError(
                f"Commande échouée : `{cmd_str}`\n"
                f"stderr: {result.stderr.strip()}"
            )
    return result


# ---------------------------------------------------------------------------
# Gestionnaire DVC principal
# ---------------------------------------------------------------------------

class DVCManager:
    """
    Interface Python pour les opérations DVC du pipeline médical.
    Gère : init, add, push, commit, tag, status, liste des versions.
    """

    def __init__(self, repo_path: str = ".", remote_name: str = "myremote"):
        self.repo_path = str(Path(repo_path).resolve())
        self.remote_name = remote_name
        self._check_dvc_installed()

    # -----------------------------------------------------------------------
    # Vérifications
    # -----------------------------------------------------------------------

    def _check_dvc_installed(self) -> None:
        """Vérifie que DVC est installé et accessible."""
        result = _run(["dvc", "--version"], check=False)
        if result.returncode != 0:
            raise DVCError(
                "DVC n'est pas installé. Lancez : pip install dvc"
            )
        version = result.stdout.strip()
        logger.info(f"DVC détecté : {version}")

    def is_initialized(self) -> bool:
        """Vérifie si DVC est initialisé dans le répertoire."""
        dvc_dir = Path(self.repo_path) / ".dvc"
        return dvc_dir.exists()

    # -----------------------------------------------------------------------
    # Initialisation
    # -----------------------------------------------------------------------

    def init(self, no_scm: bool = False) -> None:
        """
        Initialise DVC dans le repo.
        no_scm=True si Git n'est pas utilisé (déconseillé en production).
        """
        if self.is_initialized():
            logger.info("DVC déjà initialisé — skip")
            return
        cmd = ["dvc", "init"]
        if no_scm:
            cmd.append("--no-scm")
        _run(cmd, cwd=self.repo_path)
        logger.info("DVC initialisé avec succès")

    def configure_remote(
        self,
        remote_url: str,
        remote_type: str = "gdrive",
    ) -> None:
        """
        Configure le remote storage DVC.
        remote_type : 'gdrive' | 's3' | 'gcs' | 'local'
        """
        _run(
            ["dvc", "remote", "add", "-d", self.remote_name, remote_url],
            cwd=self.repo_path,
        )
        if remote_type == "gdrive":
            _run(
                ["dvc", "remote", "modify", self.remote_name, "gdrive_acknowledge_abuse", "true"],
                cwd=self.repo_path,
            )
        logger.info(f"Remote configuré : {self.remote_name} → {remote_url}")

    # -----------------------------------------------------------------------
    # Opérations sur les fichiers
    # -----------------------------------------------------------------------

    def add(self, file_path: str) -> str:
        """
        Ajoute un fichier/dossier au tracking DVC.
        Retourne le chemin du fichier .dvc créé.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Fichier introuvable : {file_path}")

        _run(["dvc", "add", str(path)], cwd=self.repo_path)
        dvc_file = str(path) + ".dvc"
        logger.info(f"Fichier tracké par DVC : {file_path} → {dvc_file}")
        return dvc_file

    def push(self, remote: Optional[str] = None) -> None:
        """Pousse les données vers le remote storage."""
        cmd = ["dvc", "push"]
        if remote:
            cmd.extend(["-r", remote])
        _run(cmd, cwd=self.repo_path)
        logger.info("Données poussées vers le remote DVC")

    def pull(self, file_path: Optional[str] = None) -> None:
        """Tire les données depuis le remote storage."""
        cmd = ["dvc", "pull"]
        if file_path:
            cmd.append(file_path + ".dvc")
        _run(cmd, cwd=self.repo_path)
        logger.info("Données tirées depuis le remote DVC")

    def repro(self) -> None:
        """Rejoue le pipeline DVC complet (dvc repro)."""
        _run(["dvc", "repro"], cwd=self.repo_path)
        logger.info("Pipeline DVC reproduit avec succès")

    # -----------------------------------------------------------------------
    # Statut et versions
    # -----------------------------------------------------------------------

    def status(self) -> dict:
        """Retourne le statut DVC sous forme de dict."""
        result = _run(["dvc", "status", "--json"], cwd=self.repo_path, check=False)
        if result.returncode == 0 and result.stdout.strip():
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return {"raw": result.stdout.strip()}
        return {}

    def diff(self) -> dict:
        """Retourne les différences DVC depuis le dernier commit."""
        result = _run(["dvc", "diff", "--json"], cwd=self.repo_path, check=False)
        if result.returncode == 0 and result.stdout.strip():
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return {}
        return {}

    def list_versions(self) -> list:
        """Retourne la liste des tags DVC/Git existants."""
        result = _run(["git", "tag", "-l"], cwd=self.repo_path, check=False)
        if result.returncode == 0:
            tags = [t.strip() for t in result.stdout.split("\n") if t.strip()]
            logger.info(f"Versions DVC disponibles : {tags}")
            return tags
        return []

    def checkout_version(self, version_tag: str) -> None:
        """Revient à une version spécifique du dataset."""
        _run(["git", "checkout", version_tag], cwd=self.repo_path)
        _run(["dvc", "checkout"], cwd=self.repo_path)
        logger.info(f"Checkout vers la version : {version_tag}")

    # -----------------------------------------------------------------------
    # Commit et tag de version
    # -----------------------------------------------------------------------

    def commit_version(
        self,
        version_tag: str,
        message: Optional[str] = None,
        files_to_stage: Optional[list] = None,
    ) -> None:
        """
        Crée un commit Git + tag DVC pour la version courante du dataset.
        files_to_stage : liste de fichiers .dvc à ajouter au commit.
        """
        if message is None:
            message = f"DVC: version {version_tag} — {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        # Stage les fichiers .dvc
        to_stage = files_to_stage or []
        for f in to_stage:
            _run(["git", "add", f], cwd=self.repo_path)

        # Commit et tag
        _run(["git", "commit", "-m", message], cwd=self.repo_path)
        _run(["git", "tag", "-a", version_tag, "-m", message], cwd=self.repo_path)
        logger.info(f"Version créée : {version_tag}")

    # -----------------------------------------------------------------------
    # Workflow complet post-pipeline
    # -----------------------------------------------------------------------

    def version_dataset(
        self,
        dataset_path: str,
        version_tag: str,
        push: bool = True,
    ) -> str:
        """
        Workflow complet de versioning d'un dataset :
        dvc add → git add .dvc → git commit + tag → dvc push.
        Retourne le tag de version créé.
        """
        logger.info(f"Versioning du dataset : {dataset_path} → {version_tag}")

        # 1. Tracker avec DVC
        dvc_file = self.add(dataset_path)

        # 2. Commit Git + tag
        self.commit_version(
            version_tag=version_tag,
            files_to_stage=[dvc_file, ".gitignore"],
        )

        # 3. Push vers remote
        if push:
            try:
                self.push()
            except DVCError as e:
                logger.warning(f"Push DVC échoué (remote non configuré ?) : {e}")

        logger.info(f"Dataset versionné avec succès : {version_tag}")
        return version_tag

    def get_dataset_info(self, dvc_file_path: str) -> dict:
        """
        Lit un fichier .dvc et retourne les métadonnées du dataset.
        """
        dvc_path = Path(dvc_file_path)
        if not dvc_path.exists():
            return {}
        try:
            import yaml
            with open(dvc_path) as f:
                return yaml.safe_load(f)
        except Exception:
            return {}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    manager = DVCManager(repo_path=".")

    print("DVC initialisé :", manager.is_initialized())
    print("Versions disponibles :", manager.list_versions())
    print("Statut DVC :", manager.status())