"""Tests de ai_generator (prompt pur + flux generate avec API mockee)."""

from __future__ import annotations

import datetime
from types import SimpleNamespace

from src.ai_generator import SYSTEM_PROMPT, AiGenerator, build_relance_prompt
from src.config import Settings
from src.models import Customer, Invoice
from src.relance_policy import LEVELS

REF = datetime.date(2026, 6, 25)


def _invoice() -> Invoice:
    return Invoice(
        id=4,
        name="FAC/2026/00004",
        customer=Customer(id=7, name="Épicerie Le Panier"),
        amount_total=1750.0,
        amount_residual=1750.0,
        invoice_date=None,
        invoice_date_due=datetime.date(2026, 6, 17),  # J+8
        payment_state="not_paid",
        currency="EUR",
    )


def test_system_prompt_interdit_historique_relances() -> None:
    # Le prompt systeme doit interdire d'inventer un historique de relances.
    assert "présume aucun historique" in SYSTEM_PROMPT
    assert "antérieur" in SYSTEM_PROMPT


def test_build_relance_prompt_contient_les_faits() -> None:
    prompt = build_relance_prompt(_invoice(), LEVELS[1], reference_date=REF)
    assert "FAC/2026/00004" in prompt
    assert "Épicerie Le Panier" in prompt
    assert "1750.00 EUR" in prompt
    assert "2026-06-17" in prompt
    assert "8 jours" in prompt
    assert "niveau 1" in prompt
    assert LEVELS[1].tone in prompt  # le ton du niveau guide la generation


def test_build_relance_prompt_statut_partiel() -> None:
    inv = Invoice(
        id=6, name="FAC/2026/00006", customer=Customer(8, "Restaurant La Marée"),
        amount_total=6400.0, amount_residual=3200.0, invoice_date=None,
        invoice_date_due=datetime.date(2026, 5, 21), payment_state="partial", currency="EUR",
    )
    prompt = build_relance_prompt(inv, LEVELS[3], reference_date=REF)
    assert "partiellement payée" in prompt
    assert "3200.00 EUR" in prompt  # on relance le reste du, pas le total


class _FakeMessages:
    """Stub du sous-objet `client.messages`."""

    def __init__(self, recorder: dict) -> None:
        self._recorder = recorder

    def create(self, **kwargs):
        self._recorder.update(kwargs)
        return SimpleNamespace(
            content=[
                SimpleNamespace(type="text", text="Objet : Relance\n\nBonjour,"),
                SimpleNamespace(type="text", text=" merci de régulariser.\nLe service comptabilité"),
            ]
        )


class _FakeClient:
    """Client Anthropic factice (aucun appel réseau)."""

    def __init__(self) -> None:
        self.calls: dict = {}
        self.messages = _FakeMessages(self.calls)


def _settings() -> Settings:
    return Settings(
        odoo_url="x", odoo_db="x", odoo_login="x", odoo_password="x",
        anthropic_api_key="sk-ant-FAKE", claude_model="claude-sonnet-4-6",
    )


def test_generate_avec_client_mocke() -> None:
    fake = _FakeClient()
    gen = AiGenerator(_settings(), client=fake)
    message = gen.generate(_invoice(), LEVELS[1], reference_date=REF)

    # Le texte des blocs est concatene et nettoye
    assert message.startswith("Objet : Relance")
    assert "Le service comptabilité" in message
    # Les bons parametres ont ete passes a l'API
    assert fake.calls["model"] == "claude-sonnet-4-6"
    assert fake.calls["max_tokens"] == 1024
    assert any(m["role"] == "user" for m in fake.calls["messages"])
