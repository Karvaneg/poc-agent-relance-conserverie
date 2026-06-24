"""Structures de données du domaine.

Dataclasses pures, sans logique métier ni I/O. Elles modélisent les factures et
clients lus depuis Odoo. La transformation des enregistrements XML-RPC bruts
(dictionnaires) en objets typés se fait via `Invoice.from_odoo` — un simple
mapping, pas de règle de relance (celle-ci vit dans `relance_policy.py`).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any


def _parse_date(value: Any) -> datetime.date | None:
    """Convertit une date Odoo (``"YYYY-MM-DD"`` ou ``False``) en `date` ou None."""
    return datetime.date.fromisoformat(value) if value else None


def _m2o(value: Any) -> tuple[int | None, str]:
    """Décompose un champ many2one Odoo (``[id, name]`` ou ``False``)."""
    if value:
        return value[0], value[1]
    return None, ""


@dataclass(frozen=True)
class Customer:
    """Client destinataire d'une relance.

    Attributes:
        id: Identifiant Odoo du partenaire (`res.partner`), ou None si absent.
        name: Nom du client.
    """

    id: int | None
    name: str


@dataclass(frozen=True)
class Invoice:
    """Facture client impayée.

    Attributes:
        id: Identifiant Odoo de la facture (`account.move`).
        name: Référence de la facture (ex. ``FAC/2026/00004``).
        customer: Client concerné.
        amount_total: Montant total TTC.
        amount_residual: Reste dû (montant de la relance).
        invoice_date: Date d'émission, si disponible.
        invoice_date_due: Date d'échéance, si disponible.
        payment_state: État de paiement Odoo (``not_paid`` ou ``partial``).
        currency: Code/nom de la devise (ex. ``EUR``).
    """

    id: int
    name: str
    customer: Customer
    amount_total: float
    amount_residual: float
    invoice_date: datetime.date | None
    invoice_date_due: datetime.date | None
    payment_state: str
    currency: str

    @classmethod
    def from_odoo(cls, record: dict[str, Any]) -> "Invoice":
        """Construit une `Invoice` à partir d'un enregistrement XML-RPC.

        Args:
            record: Dictionnaire renvoyé par `search_read` sur `account.move`
                (cf. `odoo_client.INVOICE_FIELDS`).

        Returns:
            La facture typée correspondante.
        """
        partner_id, partner_name = _m2o(record.get("partner_id"))
        _, currency_name = _m2o(record.get("currency_id"))
        return cls(
            id=record["id"],
            name=record["name"],
            customer=Customer(id=partner_id, name=partner_name),
            amount_total=float(record.get("amount_total") or 0.0),
            amount_residual=float(record.get("amount_residual") or 0.0),
            invoice_date=_parse_date(record.get("invoice_date")),
            invoice_date_due=_parse_date(record.get("invoice_date_due")),
            payment_state=record.get("payment_state") or "",
            currency=currency_name,
        )
