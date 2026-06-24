"""Tests unitaires de la logique de relance (purs, sans Odoo ni API)."""

from __future__ import annotations

import datetime

import pytest

from src.models import Customer, Invoice
from src.relance_policy import compute_level, days_overdue, relance_for

REF = datetime.date(2026, 6, 25)  # date de reference fixe pour des tests deterministes


@pytest.mark.parametrize(
    "days, expected",
    [
        (-3, 0),   # pas encore echue
        (0, 0),    # echue aujourd'hui
        (6, 0),    # sous le seuil niveau 1
        (7, 1),    # borne basse niveau 1
        (14, 1),   # borne haute niveau 1
        (15, 2),   # borne basse niveau 2
        (29, 2),   # borne haute niveau 2
        (30, 3),   # borne basse niveau 3
        (100, 3),  # tres en retard
    ],
)
def test_compute_level_bornes(days: int, expected: int) -> None:
    assert compute_level(days) == expected


def test_days_overdue() -> None:
    assert days_overdue(datetime.date(2026, 6, 17), REF) == 8
    assert days_overdue(datetime.date(2026, 6, 25), REF) == 0
    assert days_overdue(datetime.date(2026, 7, 5), REF) == -10  # echeance future


def _invoice(due: datetime.date | None) -> Invoice:
    """Fabrique une facture minimale pour les tests."""
    return Invoice(
        id=1,
        name="FAC/TEST",
        customer=Customer(id=1, name="Client Test"),
        amount_total=1000.0,
        amount_residual=1000.0,
        invoice_date=None,
        invoice_date_due=due,
        payment_state="not_paid",
        currency="EUR",
    )


@pytest.mark.parametrize(
    "due, expected_level",
    [
        (datetime.date(2026, 6, 17), 1),  # J+8
        (datetime.date(2026, 6, 5), 2),   # J+20
        (datetime.date(2026, 5, 21), 3),  # J+35
    ],
)
def test_relance_for_niveaux(due: datetime.date, expected_level: int) -> None:
    niveau = relance_for(_invoice(due), reference_date=REF)
    assert niveau is not None
    assert niveau.level == expected_level


def test_relance_for_non_echue_renvoie_none() -> None:
    assert relance_for(_invoice(datetime.date(2026, 6, 24)), reference_date=REF) is None  # J+1
    assert relance_for(_invoice(datetime.date(2026, 7, 10)), reference_date=REF) is None  # future


def test_relance_for_sans_echeance_renvoie_none() -> None:
    assert relance_for(_invoice(None), reference_date=REF) is None
