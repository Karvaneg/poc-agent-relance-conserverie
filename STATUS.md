# État d'avancement — POC agent de relance

> Récapitulatif de ce qui est livré et de ce qui reste à faire.
> Dernière mise à jour : 2026-06-25.

---

## ✅ Fait

### Infrastructure (Phase A)
- `docker-compose.yml` : **Odoo 17 + PostgreSQL 15** (réseau dédié, volumes nommés, healthcheck, `platform: linux/amd64` pour WSL2).
- Base **`conserverie`** créée sans données de démo + **seed reproductible** (`docker/fixtures/create_invoices.py`) : 2 clients, 6 factures (brouillon, 2 payées, J+8 / J+20 / J+35).

### Agent Python (Phases B & C)
- Modules : `config`, `odoo_client` (XML-RPC, **lecture seule**), `models`, `relance_policy`, `ai_generator` (Claude), `main`.
- Classification du retard **J+7 / J+15 / J+30 → niveaux 1 / 2 / 3**.
- Génération des relances via l'**API Claude** (`claude-sonnet-4-6`), ton adapté au niveau, prompt **sans historique inventé** (fix #8).
- **21 tests pytest** (logique de relance, mapping, prompt, orchestration).
- CLI : `--dry-run` (sans appel IA), `--debug`, `--reference-date`.

### Documentation & Git
- `README.md` (setup, exécution, dépannage, crédits API), `COLLABORATION.md`, `CLAUDE.md` + workspace context **Python**.
- Dépôt **GitHub public**, historique en **8 PR**, tag **`v0.1-demo`** sur `main`.

### Démo
- **Run live de bout en bout validé** : 3 relances générées, ton différencié, montants/dates exacts (reste dû, pas le total).

---

## 🔜 Reste à faire

### Court terme
- [ ] Promouvoir le fix prompt (PR #8) de **`dev` → `main`** quand souhaité (`main` est figée à `v0.1-demo`) ; option : tag `v0.1.1-demo`.
- [ ] Ajouter ta **vraie clé Anthropic** dans `.env` sur la machine de démo (déjà fait sur la machine de dev).

### Phase 2 (hors périmètre actuel)
- [ ] **Envoi réel** des relances (SMTP).
- [ ] **Écriture dans Odoo** : tracer l'historique des relances (`account.move.line` / champ dédié) → permettrait au prompt de s'appuyer sur l'**historique réel** (lève la limite à l'origine du fix #8).
- [ ] **Scheduler** : exécution automatique périodique.
- [ ] **Dashboard web** de suivi.

### Industrialisation (nice to have)
- [ ] **CI GitHub Actions** : `pytest` sur chaque push/PR.
- [ ] Config **lint/format** (`black` + `ruff`).
- [ ] Gestion **multi-devise / multi-société**.
- [ ] Tests d'intégration Odoo automatisés (aujourd'hui validés manuellement via XML-RPC).

---

## ⚠️ Limites connues (assumées pour le POC)
- **Lecture seule** côté Odoo : aucun envoi, aucune écriture.
- **Pas de suivi d'historique** des relances : le niveau découle uniquement du retard.
- **Crédits API** Anthropic requis pour la génération (facturation à l'usage, distincte de l'abonnement Claude Pro).
