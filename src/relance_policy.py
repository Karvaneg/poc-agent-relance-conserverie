"""Logique métier de relance — fonctions pures, testables sans Odoo ni API.

À partir du retard de paiement (en jours), détermine le niveau de relance et le
ton attendu. Aucune I/O, aucune dépendance à Odoo ou à Claude. Les seuils sont
des constantes ajustables (cf. brief, section 4).

Barème :
    < 7 j        -> niveau 0 : pas de relance (ignorée)
    7 à 14 j     -> niveau 1 : rappel courtois
    15 à 29 j    -> niveau 2 : relance ferme
    >= 30 j      -> niveau 3 : mise en demeure
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from src.models import Invoice

# Seuils de retard (en jours) — bornes basses inclusives de chaque niveau.
SEUIL_NIVEAU_1 = 7
SEUIL_NIVEAU_2 = 15
SEUIL_NIVEAU_3 = 30


@dataclass(frozen=True)
class RelanceLevel:
    """Niveau de relance et ton associé.

    Attributes:
        level: Numéro du niveau (1, 2 ou 3).
        label: Libellé court du niveau.
        tone: Description du ton attendu, destinée à guider la génération IA.
    """

    level: int
    label: str
    tone: str


# Définition des trois niveaux de relance.
LEVELS: dict[int, RelanceLevel] = {
    1: RelanceLevel(
        level=1,
        label="Rappel courtois",
        tone=(
            "Aimable et compréhensif. Présomption d'un simple oubli. Rappeler "
            "poliment l'échéance dépassée et les modalités de règlement."
        ),
    ),
    2: RelanceLevel(
        level=2,
        label="Relance ferme",
        tone=(
            "Plus direct et ferme, tout en restant professionnel. Souligner que "
            "l'échéance est dépassée depuis plusieurs semaines et demander un "
            "règlement rapide."
        ),
    ),
    3: RelanceLevel(
        level=3,
        label="Mise en demeure",
        tone=(
            "Formel et solennel. Mentionner les suites possibles en cas de "
            "non-règlement, sur un ton juridique mesuré, sans agressivité."
        ),
    ),
}


def days_overdue(
    due_date: datetime.date, reference_date: datetime.date | None = None
) -> int:
    """Calcule le nombre de jours de retard.

    Args:
        due_date: Date d'échéance de la facture.
        reference_date: Date servant de « aujourd'hui ». Par défaut, la date du jour.

    Returns:
        Le retard en jours (positif si l'échéance est dépassée, négatif sinon).
    """
    today = reference_date or datetime.date.today()
    return (today - due_date).days


def compute_level(days: int) -> int:
    """Détermine le niveau de relance à partir du retard.

    Args:
        days: Nombre de jours de retard.

    Returns:
        Le niveau de relance (1, 2 ou 3), ou 0 si aucune relance n'est due.
    """
    if days >= SEUIL_NIVEAU_3:
        return 3
    if days >= SEUIL_NIVEAU_2:
        return 2
    if days >= SEUIL_NIVEAU_1:
        return 1
    return 0


def relance_for(
    invoice: Invoice, reference_date: datetime.date | None = None
) -> RelanceLevel | None:
    """Détermine le niveau de relance applicable à une facture.

    Args:
        invoice: La facture à évaluer.
        reference_date: Date servant de « aujourd'hui ». Par défaut, la date du jour.

    Returns:
        Le `RelanceLevel` applicable, ou None si la facture ne doit pas être
        relancée (pas d'échéance, ou retard inférieur au seuil du niveau 1).
    """
    if invoice.invoice_date_due is None:
        return None
    level = compute_level(days_overdue(invoice.invoice_date_due, reference_date))
    return LEVELS.get(level)
