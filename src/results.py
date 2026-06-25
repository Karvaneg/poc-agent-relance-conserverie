"""Résultat structuré d'une relance — pont entre la logique et les rendus.

Une `RelanceResult` agrège, pour une facture donnée, son niveau de relance, le
retard calculé et le message généré (ou son absence en dry-run / en cas
d'échec). C'est cette structure que consomment les rendus (console, HTML), de
sorte que `main.run` calcule une fois et affiche de plusieurs façons.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.models import Invoice
from src.relance_policy import RelanceLevel


@dataclass(frozen=True)
class RelanceResult:
    """Issue du traitement d'une facture à relancer.

    Attributes:
        invoice: La facture concernée.
        level: Le niveau de relance retenu.
        days_overdue: Retard en jours à la date de référence.
        message: Le message généré, ou None (dry-run, ou échec).
        error: Message d'erreur si la génération a échoué, sinon None.
    """

    invoice: Invoice
    level: RelanceLevel
    days_overdue: int
    message: str | None = None
    error: str | None = None
