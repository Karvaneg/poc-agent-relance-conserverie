---
name: project-brief
description: Brief technique du POC agent-relance-conserverie — objectif, stack, architecture, hypothèses Odoo, conventions. À lire avant toute action sur le code.
---

# Project Brief — poc-agent-relance-conserverie

> Document de référence écrit à la main. Source de vérité sur le **quoi** et le **comment** du projet.
> Ne pas confondre avec `project-context.md` (arborescence auto-générée).

---

## 1. Objectif & Périmètre

**Objectif :** POC d'un agent IA (Claude via Anthropic API) qui automatise les relances de factures impayées pour une PME comptable (3 comptables, ERP Odoo). Cible : démo fonctionnelle et présentable en entretien sous 1-2 semaines.

### IN — ce que le POC fait (Phase 1)

- Lancer un Odoo 17 local via Docker (avec données de démo).
- Se connecter à Odoo en **XML-RPC** depuis un agent Python.
- Récupérer les factures clients **impayées et échues**.
- Catégoriser chaque facture par **niveau de relance** selon le retard (J+7 / J+15 / J+30).
- Générer pour chaque facture un **message de relance** rédigé par Claude, adapté au niveau et au client.
- **Afficher** les résultats en console (tableau récap + messages générés).

### OUT — ce que le POC ne fait PAS (hors périmètre Phase 1)

- ❌ **Aucun envoi réel** de mail / SMS / courrier. Génération et affichage uniquement.
- ❌ Pas d'écriture dans Odoo (lecture seule sur les factures).
- ❌ Pas de déploiement cloud, pas d'Odoo SaaS — tout est local Docker.
- ❌ Pas d'interface web / front. Sortie console (et éventuellement fichier).
- ❌ Pas de gestion multi-société, multi-devise avancée, ni de relance par téléphone.
- ❌ Pas d'authentification utilisateur ni de file d'attente / scheduler en Phase 1.

### Anticipation Phase 2 (hors scope aujourd'hui)

Le POC Phase 1 **génère et affiche**. La Phase 2 — **non implémentée maintenant**, mentionnée pour donner sa cohérence au design — pourrait ajouter : envoi réel par **SMTP**, **écriture des relances dans Odoo** (`account.move.line` / suivi d'historique), **scheduler** pour exécution automatique, et **dashboard web**. La structure modulaire du POC (I/O isolée dans `odoo_client` / `ai_generator`, logique métier pure dans `relance_policy`) doit permettre ces extensions **sans refactoring majeur** : un module d'envoi viendrait s'ajouter en aval de la génération, sans toucher au cœur.

---

## 2. Stack Technique

| Composant               | Version cible                       | Rôle                                                                                               |
| ----------------------- | ----------------------------------- | -------------------------------------------------------------------------------------------------- |
| Python                  | **3.11+**                           | Langage de l'agent                                                                                 |
| Docker + Docker Compose | récent                              | Orchestration Odoo + PostgreSQL en local                                                           |
| Odoo                    | **17** (image officielle `odoo:17`) | ERP source des factures                                                                            |
| PostgreSQL              | **15** (image `postgres:15`)        | Base de données d'Odoo                                                                             |
| Anthropic Claude API    | SDK `anthropic` ≥ 0.40              | Génération des messages de relance                                                                 |
| Modèle Claude (défaut)  | `claude-sonnet-4-6`                 | Bon rapport coût/latence/qualité pour la rédaction. `claude-opus-4-8` si la qualité prime en démo. |

**Communication Odoo ↔ agent :** XML-RPC via le module standard `xmlrpc.client` (bibliothèque standard Python, **aucune dépendance externe**). Endpoints :

- `/xmlrpc/2/common` → `authenticate(db, login, password, {})` → renvoie `uid`.
- `/xmlrpc/2/object` → `execute_kw(db, uid, password, model, method, args, kwargs)`.

---

## 3. Architecture

Structure modulaire. Chaque module a une responsabilité unique (SRP).

```
poc-agent-relance-conserverie/
├── .claude/skills/            # Contexte & règles pour Claude Code
│   ├── project-brief.md       # CE fichier
│   └── working-rules.md       # Règles de travail
├── docker/
│   └── docker-compose.yml     # Odoo 17 + PostgreSQL 15
├── src/
│   ├── __init__.py
│   ├── config.py              # Chargement .env, dataclass Settings (URL, db, login, clé API)
│   ├── odoo_client.py         # Connexion XML-RPC + requêtes factures (lecture seule)
│   ├── models.py              # Dataclasses : Invoice, Customer, RelanceLevel
│   ├── relance_policy.py      # Logique métier : retard -> niveau de relance
│   ├── ai_generator.py        # Appel Claude API, prompt + génération message
│   └── main.py                # Orchestration : fetch -> classify -> generate -> display
├── tests/
│   ├── test_relance_policy.py # Tests unitaires de la logique de relance (sans I/O)
│   └── test_ai_generator.py   # Test du formatage de prompt (API mockée)
├── .env.example               # Modèle de variables d'environnement (sans secrets)
├── requirements.txt
└── README.md
```

**Responsabilités :**

- `config.py` — Charge `.env`, expose un objet `Settings` typé. Échoue tôt et clairement si une variable manque.
- `odoo_client.py` — Encapsule XML-RPC. Méthodes : `authenticate()`, `fetch_unpaid_invoices()`. Ne contient **aucune logique métier de relance**.
- `models.py` — Structures de données pures (`@dataclass`). Pas de logique, pas d'I/O.
- `relance_policy.py` — Fonctions pures : à partir du retard en jours, retourne le niveau (1/2/3) et le ton attendu. **Testable sans Odoo ni API.**
- `ai_generator.py` — Construit le prompt à partir d'une `Invoice` + niveau, appelle Claude, retourne le texte. Aucune dépendance à Odoo.
- `main.py` — Le seul point d'entrée. Orchestre, gère les erreurs de haut niveau, affiche.

**Principe :** I/O (Odoo, API) isolée dans `odoo_client.py` / `ai_generator.py` ; logique métier pure et testable dans `relance_policy.py`.

---

## 4. Hypothèses Odoo

> À valider lors du setup Docker. Les nommer ici évite les suppositions silencieuses.

### Modules à installer

- **`account`** (Comptabilité / Facturation) — fournit le modèle `account.move`. C'est le seul module strictement requis.
- Données de démo Odoo activées (`--load-language` / base avec demo data) pour avoir des factures et clients de test.

### Modèle & champs exploités

**`account.move`** (factures) — lecture seule :

| Champ              | Type      | Usage                                          |
| ------------------ | --------- | ---------------------------------------------- |
| `name`             | char      | Référence facture (ex. `INV/2026/0001`)        |
| `move_type`        | selection | Filtrer sur `out_invoice` (facture client)     |
| `state`            | selection | Filtrer sur `posted` (comptabilisée)           |
| `payment_state`    | selection | `not_paid` ou `partial` = impayée              |
| `partner_id`       | many2one  | Lien vers le client (`res.partner`)            |
| `amount_total`     | monetary  | Montant TTC                                    |
| `amount_residual`  | monetary  | Reste dû (montant de la relance)               |
| `invoice_date`     | date      | Date de facture                                |
| `invoice_date_due` | date      | **Date d'échéance** — base du calcul de retard |
| `currency_id`      | many2one  | Devise                                         |

**`res.partner`** (clients) :

| Champ   | Usage                                                      |
| ------- | ---------------------------------------------------------- |
| `name`  | Nom du client (personnalisation du message)                |
| `email` | Destinataire théorique (non utilisé pour envoi en Phase 1) |
| `lang`  | Langue (par défaut `fr_FR`)                                |

**Domaine de filtre des impayés échus :**

```python
[
    ("move_type", "=", "out_invoice"),
    ("state", "=", "posted"),
    ("payment_state", "in", ["not_paid", "partial"]),
    ("invoice_date_due", "<", today),
]
```

### Délais & niveaux de relance

Retard calculé en jours : `today - invoice_date_due`.

| Niveau                  | Retard    | Ton du message                                                         |
| ----------------------- | --------- | ---------------------------------------------------------------------- |
| **1 — Rappel courtois** | 7 à 14 j  | Aimable, présomption d'oubli, rappel des coordonnées de paiement       |
| **2 — Relance ferme**   | 15 à 29 j | Plus direct, rappelle l'échéance dépassée, demande un règlement rapide |
| **3 — Mise en demeure** | ≥ 30 j    | Formel, mentionne les suites possibles, ton juridique mesuré           |

Retard < 7 j : **pas de relance** (ignorée). Ces seuils sont des constantes configurables dans `relance_policy.py`.

### Données de test requises

Le POC s'exécute en lecture seule. Pour valider la chaîne complète avant la démo, créer **au minimum 6 factures de test** en Odoo couvrant les variantes suivantes :

- 1 brouillon (`state = draft`) — doit être **ignorée**.
- 2 payées (`payment_state = paid`) — doivent être **ignorées**.
- 1 partiellement payée (`payment_state = partial`) échue — doit être **relancée**.
- 1 impayée échue à **J+8** → niveau 1.
- 1 impayée échue à **J+20** → niveau 2.
- 1 impayée échue à **J+35** → niveau 3.

Via un script de seed ou un dump de données saisi à la main. **À documenter dans la section setup du `README.md`** (création des données + valeurs attendues), pour rendre la démo reproductible.

### Validation au démarrage

`main.py` doit **valider que ces hypothèses sont respectées** au lancement : module `account` présent, champs attendus disponibles sur `account.move`, domaine de filtre applicable. En cas d'erreur (champ manquant, module `account` absent, connexion impossible), **échouer tôt avec un message explicite** plutôt que de laisser un `KeyError` (ou équivalent) survenir en cours d'exécution.

---

## 5. Conventions de Code

- **Langage** : Python 3.11+, typé (type hints partout sur signatures publiques).
- **Naming** :
  - modules & fonctions & variables → `snake_case`
  - classes & dataclasses → `PascalCase`
  - constantes → `UPPER_SNAKE_CASE`
- **Docstrings** : **style Google**, sur tout module, classe et fonction publique.

  ```python
  def compute_relance_level(days_overdue: int) -> int:
      """Détermine le niveau de relance selon le retard.

      Args:
          days_overdue: Nombre de jours de retard (today - date d'échéance).

      Returns:
          Le niveau de relance (1, 2 ou 3), ou 0 si aucune relance n'est due.
      """
  ```

- **Logging** : module standard `logging`, **jamais de `print`** pour le diagnostic (le `print` est réservé à l'affichage final destiné à l'utilisateur).

  ```python
  import logging
  logger = logging.getLogger(__name__)
  logging.basicConfig(level=logging.INFO,
                      format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
  ```

  - `INFO` : étapes normales (connexion Odoo, N factures récupérées).
  - `WARNING` : situation anormale non bloquante (client sans email).
  - `ERROR` : échec d'une opération (avec contexte).
  - **Jamais** de secret (clé API, mot de passe) dans les logs.

- **Gestion des erreurs** : `try/except` explicites (jamais d'`except:` nu). Logger l'erreur complète côté diagnostic — `logger.error("...", exc_info=True)` — et afficher à l'utilisateur un message **clair et court**. **Jamais de traceback brut en console**, sauf en mode debug.
- **Formatage** : `black` (ligne 88) + `ruff` pour le lint. Imports ordonnés.
- **Fonctions courtes**, une responsabilité. Logique métier = fonctions pures sans effet de bord.

---

## 6. Sécurité & Credentials

- **Aucun secret en dur dans le code.** Jamais. Ni clé API, ni mot de passe Odoo.
- Tous les secrets passent par un fichier **`.env`** (déjà couvert par `.gitignore`), chargé via `python-dotenv` dans `config.py`.
- Un **`.env.example`** versionné documente les variables attendues, **sans valeurs réelles** :

  ```
  # Odoo
  ODOO_URL=http://localhost:8069
  ODOO_DB=conserverie
  ODOO_LOGIN=admin
  ODOO_PASSWORD=changeme

  # Anthropic
  ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
  CLAUDE_MODEL=claude-sonnet-4-6
  ```

- `config.py` **valide la présence** de chaque variable au démarrage et lève une erreur explicite si une manque (échec rapide).
- La clé API n'apparaît jamais dans les logs, les messages d'erreur, ni la sortie console.
- Rappel : `.env`, `.env.*` (sauf `.env.example`) sont déjà gitignorés.

---

## 7. Dépendances

`requirements.txt` — **minimal, pas de dépendances exotiques**. Justification requise pour tout ajout.

```
anthropic>=0.40          # SDK officiel Claude
python-dotenv>=1.0       # chargement du .env
```

**Dépendances de développement** (optionnel, `requirements-dev.txt`) :

```
pytest>=8.0
black>=24.0
ruff>=0.6
```

**Notes :**

- **XML-RPC** : aucune lib externe — `xmlrpc.client` est dans la bibliothèque standard. On n'ajoute **pas** `odoorpc`/`odoo-xmlrpc` sauf besoin avéré.
- **HTTP** : pas besoin de `requests` pour le POC (XML-RPC stdlib + SDK anthropic suffisent). Ne l'ajouter que si un besoin HTTP direct apparaît.
- Toute nouvelle dépendance doit être validée explicitement (cf. `working-rules.md` → Limites).

### Validation d'une nouvelle dépendance

Avant tout ajout au `requirements.txt`, vérifier dans l'ordre :

1. **Pas déjà en stdlib** — la bibliothèque standard Python couvre-t-elle le besoin ? (ex. `xmlrpc.client` pour XML-RPC, `json` pour la sérialisation, `datetime` pour les dates, `pathlib` pour les chemins...).
2. **Pas de dépendances cachées lourdes** — inspecter l'arbre transitif (`pip show <pkg>`, voir `Requires`) ; refuser si elle tire une longue chaîne disproportionnée pour un POC.
3. **Bien maintenue** — dernière release récente, projet actif, adoption raisonnable.

**En cas de doute : consulter le lead avant d'ajouter.**
