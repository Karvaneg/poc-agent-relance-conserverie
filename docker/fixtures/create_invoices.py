#!/usr/bin/env python3
"""Seed de donnees de demonstration controlees pour le POC.

Cree 2 clients et 6 factures couvrant les variantes du brief (section 4) :

    1. Brouillon (draft)              -> ignoree par l'agent
    2. Payee (paid)                   -> ignoree
    3. Payee (paid)                   -> ignoree
    4. Impayee echue a J+8            -> relance niveau 1 (courtois)
    5. Impayee echue a J+20           -> relance niveau 2 (ferme)
    6. Partiellement payee, echue J+35-> relance niveau 3 (mise en demeure)

Les echeances sont calculees par rapport a la date du jour, donc la demo
reste coherente quel que soit le jour ou le seed est rejoue.

OUTIL DE FIXTURES/SETUP : ce script ECRIT dans Odoo (exception assumee a la
regle "lecture seule", qui ne s'applique qu'a l'agent runtime). Il est concu
pour une base VIERGE (sans donnees de demo). Le relancer sur une base deja
seedee creera des doublons -> dans ce cas, recreer la base d'abord.

Usage :
    python docker/fixtures/create_invoices.py            # lit .env si present
    python docker/fixtures/create_invoices.py --env .env
    python docker/fixtures/create_invoices.py --url http://localhost:8069 \
        --db conserverie --login admin@conserverie.fr --password admin
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys
import xmlrpc.client

# --- Parametrage des clients et factures ------------------------------------

CUSTOMERS = {
    "A": {"name": "Épicerie Le Panier", "email": "compta@epicerie-lepanier.fr"},
    "B": {"name": "Restaurant La Marée", "email": "compta@restaurant-lamaree.fr"},
}

# (cle_client, libelle ligne, montant HT, jours_de_retard|None, statut_cible)
# statut_cible : "draft" | "paid" | "unpaid" | "partial"
INVOICES = [
    ("A", "Conserves de sardines - lot brouillon", 480.0, None, "draft"),
    ("A", "Terrines maison - commande reglee", 1250.0, -5, "paid"),
    ("B", "Rillettes de thon - commande reglee", 940.0, -3, "paid"),
    ("A", "Conserves de maquereaux - lot 1", 1750.0, 8, "unpaid"),
    ("B", "Soupes de poisson - lot saison", 3200.0, 20, "unpaid"),
    ("B", "Plateau conserves premium - gros volume", 6400.0, 35, "partial"),
]


# --- Configuration de connexion ---------------------------------------------

def load_env(path: str) -> dict[str, str]:
    """Lit un fichier .env minimaliste (KEY=VALUE) en ignorant commentaires."""
    values: dict[str, str] = {}
    if not os.path.isfile(path):
        return values
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            values[key.strip()] = val.strip()
    return values


def resolve_config(args: argparse.Namespace) -> dict[str, str]:
    """Combine .env, variables d'environnement et arguments CLI (CLI prioritaire)."""
    env = load_env(args.env)
    cfg = {
        "url": args.url or os.environ.get("ODOO_URL") or env.get("ODOO_URL") or "http://localhost:8069",
        "db": args.db or os.environ.get("ODOO_DB") or env.get("ODOO_DB") or "conserverie",
        "login": args.login or os.environ.get("ODOO_LOGIN") or env.get("ODOO_LOGIN") or "admin@conserverie.fr",
        "password": args.password or os.environ.get("ODOO_PASSWORD") or env.get("ODOO_PASSWORD") or "admin",
    }
    return cfg


# --- Client XML-RPC ---------------------------------------------------------

class Odoo:
    """Petit wrapper XML-RPC pour le seed (ecriture)."""

    def __init__(self, url: str, db: str, login: str, password: str):
        self.db = db
        self.password = password
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        self.uid = common.authenticate(db, login, password, {})
        if not self.uid:
            raise SystemExit(
                f"Authentification Odoo refusee (db={db}, login={login}). "
                "Verifier les identifiants (login = email saisi a la creation de la base)."
            )
        self.models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    def call(self, model: str, method: str, *args, **kwargs):
        return self.models.execute_kw(self.db, self.uid, self.password, model, method, list(args), kwargs)


# --- Seed --------------------------------------------------------------------

def get_accounting_refs(odoo: Odoo) -> tuple[int, int]:
    """Retourne (id du journal de vente, id d'un compte de revenu)."""
    journals = odoo.call("account.journal", "search", [("type", "=", "sale")], limit=1)
    accounts = odoo.call("account.account", "search", [("account_type", "=", "income")], limit=1)
    if not journals:
        raise SystemExit("Aucun journal de vente : la comptabilite n'est pas configuree.")
    if not accounts:
        raise SystemExit("Aucun compte de revenu : le plan comptable n'est pas installe.")
    return journals[0], accounts[0]


def ensure_customer(odoo: Odoo, name: str, email: str) -> int:
    """Cree le client s'il n'existe pas deja (par nom), renvoie son id."""
    existing = odoo.call("res.partner", "search", [("name", "=", name)], limit=1)
    if existing:
        return existing[0]
    return odoo.call("res.partner", "create", {
        "name": name,
        "email": email,
        "customer_rank": 1,
        "company_type": "company",
    })


def create_invoice(odoo: Odoo, partner_id: int, journal_id: int, income_account_id: int,
                   label: str, amount: float, days_overdue: int | None) -> int:
    """Cree une facture client en brouillon (ligne sans produit, sans taxe)."""
    today = datetime.date.today()
    if days_overdue is None:
        due = today + datetime.timedelta(days=30)        # echeance future (cas brouillon/paye)
        invoice_date = today
    else:
        due = today - datetime.timedelta(days=days_overdue)
        invoice_date = due - datetime.timedelta(days=30)  # emise 30 j avant l'echeance

    return odoo.call("account.move", "create", {
        "move_type": "out_invoice",
        "partner_id": partner_id,
        "journal_id": journal_id,
        "invoice_date": invoice_date.isoformat(),
        "invoice_date_due": due.isoformat(),
        "invoice_payment_term_id": False,   # pas de condition de paiement -> on impose l'echeance
        "invoice_line_ids": [(0, 0, {
            "name": label,
            "quantity": 1,
            "price_unit": amount,
            "account_id": income_account_id,
            "tax_ids": [(6, 0, [])],        # aucune taxe -> montant total = price_unit
        })],
    })


def register_payment(odoo: Odoo, move_id: int, amount: float) -> None:
    """Enregistre un paiement (total ou partiel) via le wizard standard."""
    ctx = {"active_model": "account.move", "active_ids": [move_id]}
    wizard_id = odoo.call(
        "account.payment.register", "create",
        {"amount": amount, "payment_date": datetime.date.today().isoformat()},
        context=ctx,
    )
    odoo.call("account.payment.register", "action_create_payments", [wizard_id], context=ctx)


def run(odoo: Odoo) -> None:
    journal_id, income_account_id = get_accounting_refs(odoo)
    partner_ids = {key: ensure_customer(odoo, c["name"], c["email"]) for key, c in CUSTOMERS.items()}
    print(f"Clients : " + ", ".join(f"{CUSTOMERS[k]['name']} (id={v})" for k, v in partner_ids.items()))

    print("\nFactures :")
    for client_key, label, amount, days_overdue, target in INVOICES:
        move_id = create_invoice(
            odoo, partner_ids[client_key], journal_id, income_account_id, label, amount, days_overdue
        )

        if target == "draft":
            status = "brouillon (draft)"
        else:
            odoo.call("account.move", "action_post", [move_id])
            if target == "paid":
                register_payment(odoo, move_id, amount)
                status = "payee"
            elif target == "partial":
                register_payment(odoo, move_id, round(amount / 2, 2))
                status = f"partiellement payee ({amount/2:.0f}/{amount:.0f})"
            else:  # unpaid
                status = "impayee (echue)"

        due_txt = "-" if days_overdue is None else (
            f"J+{days_overdue}" if days_overdue > 0 else f"J{days_overdue}"
        )
        print(f"  id={move_id:<4} {CUSTOMERS[client_key]['name']:22} {due_txt:6} {status}")

    print("\nSeed termine. Verifier avec l'agent (lecture seule) ou dans Odoo.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed de factures de demonstration pour le POC.")
    parser.add_argument("--env", default=".env", help="Fichier .env a lire (defaut: .env)")
    parser.add_argument("--url", help="URL Odoo (sinon ODOO_URL / .env / defaut)")
    parser.add_argument("--db", help="Base Odoo (sinon ODOO_DB / .env / defaut)")
    parser.add_argument("--login", help="Login Odoo (sinon ODOO_LOGIN / .env / defaut)")
    parser.add_argument("--password", help="Mot de passe Odoo (sinon ODOO_PASSWORD / .env / defaut)")
    args = parser.parse_args()

    cfg = resolve_config(args)
    print(f"Connexion : {cfg['login']} @ {cfg['url']} (db={cfg['db']})")
    odoo = Odoo(cfg["url"], cfg["db"], cfg["login"], cfg["password"])
    print(f"Authentifie (uid={odoo.uid}).\n")
    run(odoo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
