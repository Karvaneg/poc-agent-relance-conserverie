"""Tests d'orchestration de main.run (faux Odoo + faux generateur, sans reseau)."""

from __future__ import annotations

import datetime

from src.config import Settings
from src.main import run

REF = datetime.date(2026, 6, 25)


def _settings() -> Settings:
    return Settings(
        odoo_url="x", odoo_db="x", odoo_login="x", odoo_password="x",
        anthropic_api_key="sk-ant-FAKE", claude_model="claude-sonnet-4-6",
    )


def _record(name: str, partner: str, due: str, residual: float, payment_state: str) -> dict:
    return {
        "id": hash(name) & 0xFFFF, "name": name, "partner_id": [1, partner],
        "amount_total": residual, "amount_residual": residual,
        "invoice_date": False, "invoice_date_due": due,
        "payment_state": payment_state, "currency_id": [1, "EUR"],
    }


class _FakeOdoo:
    def __init__(self, records: list[dict]) -> None:
        self._records = records
        self.connected = False
        self.checked = False

    def connect(self) -> None:
        self.connected = True

    def check_environment(self) -> None:
        self.checked = True

    def fetch_unpaid_invoices(self, reference_date=None) -> list[dict]:
        return self._records


class _FakeGenerator:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, invoice, level, reference_date=None) -> str:
        self.calls += 1
        return f"MESSAGE niveau {level.level} pour {invoice.name}"


def _records() -> list[dict]:
    return [
        _record("FAC/2026/00004", "Épicerie Le Panier", "2026-06-17", 1750.0, "not_paid"),  # J+8 -> n1
        _record("FAC/2026/00005", "Restaurant La Marée", "2026-06-05", 3200.0, "not_paid"),  # J+20 -> n2
        _record("FAC/2026/00006", "Restaurant La Marée", "2026-05-21", 3200.0, "partial"),   # J+35 -> n3
        _record("FAC/2026/00009", "Client Court", "2026-06-22", 500.0, "not_paid"),          # J+3 -> ignore
    ]


def test_run_genere_les_trois_relances() -> None:
    odoo = _FakeOdoo(_records())
    gen = _FakeGenerator()
    lines: list[str] = []

    n = run(_settings(), odoo_client=odoo, generator=gen, reference_date=REF, out=lines.append)

    assert odoo.connected and odoo.checked
    assert n == 3                      # 3 a relancer (la J+3 est ignoree)
    assert gen.calls == 3
    text = "\n".join(lines)
    assert "3 à relancer" in text
    assert "sous le seuil < J+7, ignorée" in text
    for ref in ("FAC/2026/00004", "FAC/2026/00005", "FAC/2026/00006"):
        assert ref in text
    assert "MESSAGE niveau 3 pour FAC/2026/00006" in text


def test_run_dry_run_ne_genere_pas() -> None:
    gen = _FakeGenerator()
    lines: list[str] = []

    n = run(_settings(), odoo_client=_FakeOdoo(_records()), generator=gen,
            reference_date=REF, generate=False, out=lines.append)

    assert n == 3
    assert gen.calls == 0              # aucun appel IA en dry-run
    assert "génération IA ignorée" in "\n".join(lines)
