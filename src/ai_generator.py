"""Génération des messages de relance via l'API Claude (Anthropic).

Ce module construit un prompt à partir d'une facture et de son niveau de relance,
puis appelle Claude pour produire le texte du message. La construction du prompt
(`build_relance_prompt`) est une fonction pure, testable sans réseau ; seul
`AiGenerator.generate` effectue l'appel API.

Aucune dépendance à Odoo. La clé API provient de la configuration (jamais loggée).
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

import anthropic

from src.config import Settings
from src.models import Invoice
from src.relance_policy import RelanceLevel, days_overdue

logger = logging.getLogger(__name__)

# Longueur de sortie : un message de relance est court.
MAX_TOKENS = 1024

SYSTEM_PROMPT = (
    "Tu es l'assistant du service comptabilité d'une PME (une conserverie). "
    "Tu rédiges des messages de relance de factures impayées, en français, "
    "professionnels, personnalisés et prêts à être envoyés par e-mail. "
    "Règles : appuie-toi uniquement sur les informations fournies (montants, "
    "dates, références) sans en inventer ; n'utilise aucun champ à compléter "
    "entre crochets ; adapte strictement le ton au niveau de relance indiqué ; "
    "structure le message avec une ligne 'Objet :' puis le corps ; termine par "
    "une formule de politesse et la signature « Le service comptabilité ». "
    "Réponds uniquement avec le message, sans commentaire ni explication."
)


def build_relance_prompt(
    invoice: Invoice, level: RelanceLevel, reference_date: datetime.date | None = None
) -> str:
    """Construit le prompt utilisateur pour la génération d'un message de relance.

    Fonction pure (aucune I/O), afin d'être testable sans appel réseau.

    Args:
        invoice: La facture concernée.
        level: Le niveau de relance déterminé par `relance_policy`.
        reference_date: Date servant de « aujourd'hui ». Par défaut, la date du jour.

    Returns:
        Le texte du prompt à envoyer au modèle.
    """
    retard = days_overdue(invoice.invoice_date_due, reference_date) if invoice.invoice_date_due else 0
    echeance = invoice.invoice_date_due.isoformat() if invoice.invoice_date_due else "inconnue"
    return (
        f"Rédige une relance de niveau {level.level} ({level.label}).\n"
        f"Ton attendu : {level.tone}\n\n"
        "Informations de la facture :\n"
        f"- Client : {invoice.customer.name}\n"
        f"- Référence facture : {invoice.name}\n"
        f"- Montant restant dû : {invoice.amount_residual:.2f} {invoice.currency}\n"
        f"- Date d'échéance : {echeance}\n"
        f"- Retard : {retard} jours\n"
        f"- Statut de paiement : "
        f"{'partiellement payée' if invoice.payment_state == 'partial' else 'non payée'}\n"
    )


def _extract_text(response: Any) -> str:
    """Concatène les blocs de texte d'une réponse Messages API."""
    parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
    return "\n".join(parts).strip()


class AiGenerator:
    """Génère les messages de relance via Claude.

    Attributes:
        model: Identifiant du modèle Claude utilisé.
    """

    def __init__(self, settings: Settings, client: Any | None = None):
        """Initialise le générateur.

        Args:
            settings: Configuration (clé API et modèle).
            client: Client Anthropic à injecter (pour les tests). Par défaut, un
                client réel construit à partir de la clé de configuration.
        """
        self.model = settings.claude_model
        # La clé n'est jamais loggée ; le client la conserve en interne.
        self._client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def generate(
        self, invoice: Invoice, level: RelanceLevel, reference_date: datetime.date | None = None
    ) -> str:
        """Génère le message de relance pour une facture et un niveau donnés.

        Args:
            invoice: La facture à relancer.
            level: Le niveau de relance applicable.
            reference_date: Date servant de « aujourd'hui ».

        Returns:
            Le texte du message de relance généré.
        """
        prompt = build_relance_prompt(invoice, level, reference_date)
        logger.info("Génération relance niveau %s pour %s…", level.level, invoice.name)
        response = self._client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return _extract_text(response)
