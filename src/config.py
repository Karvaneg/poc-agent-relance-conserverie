"""Chargement et validation de la configuration du POC.

La configuration provient exclusivement de variables d'environnement (fichier
`.env` à la racine, jamais commité). Aucun secret n'est codé en dur. La
validation échoue tôt et clairement si une variable requise manque.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Modèle Claude par défaut si CLAUDE_MODEL n'est pas renseigné.
DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-6"

# Variables obligatoires (doivent être présentes ET non vides).
_REQUIRED = ("ODOO_URL", "ODOO_DB", "ODOO_LOGIN", "ODOO_PASSWORD", "ANTHROPIC_API_KEY")


class ConfigError(RuntimeError):
    """Levée quand la configuration est incomplète ou invalide."""


@dataclass(frozen=True)
class Settings:
    """Configuration applicative validée.

    Attributes:
        odoo_url: URL de l'instance Odoo (ex. http://localhost:8069).
        odoo_db: Nom de la base Odoo.
        odoo_login: Login Odoo (l'email saisi à la création de la base).
        odoo_password: Mot de passe du compte Odoo.
        anthropic_api_key: Clé API Anthropic.
        claude_model: Identifiant du modèle Claude à utiliser.
    """

    odoo_url: str
    odoo_db: str
    odoo_login: str
    odoo_password: str
    anthropic_api_key: str
    claude_model: str

    def __repr__(self) -> str:
        """Représentation masquant les secrets (jamais de mot de passe / clé en clair)."""
        return (
            "Settings("
            f"odoo_url={self.odoo_url!r}, odoo_db={self.odoo_db!r}, "
            f"odoo_login={self.odoo_login!r}, odoo_password='***', "
            f"anthropic_api_key='***', claude_model={self.claude_model!r})"
        )


def load_settings(env_file: str | None = ".env") -> Settings:
    """Charge et valide la configuration depuis l'environnement.

    Le fichier `.env` est chargé s'il existe (sans écraser les variables déjà
    définies dans l'environnement). Les variables de `_REQUIRED` doivent être
    présentes et non vides.

    Args:
        env_file: Chemin du fichier `.env` à charger, ou None pour ne lire que
            l'environnement courant.

    Returns:
        Les `Settings` validés.

    Raises:
        ConfigError: Si une variable requise est absente ou vide.
    """
    if env_file is not None:
        # override=False : une variable déjà présente dans l'environnement gagne.
        load_dotenv(env_file, override=False)

    missing = [name for name in _REQUIRED if not os.environ.get(name, "").strip()]
    if missing:
        raise ConfigError(
            "Variables d'environnement manquantes ou vides : "
            + ", ".join(missing)
            + ". Copier .env.example en .env et renseigner ces valeurs."
        )

    return Settings(
        odoo_url=os.environ["ODOO_URL"].strip(),
        odoo_db=os.environ["ODOO_DB"].strip(),
        odoo_login=os.environ["ODOO_LOGIN"].strip(),
        odoo_password=os.environ["ODOO_PASSWORD"].strip(),
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"].strip(),
        claude_model=(os.environ.get("CLAUDE_MODEL", "").strip() or DEFAULT_CLAUDE_MODEL),
    )
