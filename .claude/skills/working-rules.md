---
name: working-rules
description: Règles de travail avec Claude Code sur ce POC — validation avant exécution, génération de code, workflow Git, limites. À lire avant toute action.
---

# Working Rules — poc-agent-relance-conserverie

> Règles impératives pour toute contribution de Claude Code sur ce repo.
> Complète `project-brief.md` (le *quoi*) avec le *comment travailler*.

---

## 1. Interaction avec Claude Code

**Règle d'or : « montre-moi avant de lancer ».**

- Avant toute commande qui **modifie l'état** (install, build, `docker compose up`, migration, écriture de fichier importante), **annoncer ce qui va être fait** et attendre la validation.
- Avant de **créer ou modifier plusieurs fichiers**, présenter d'abord le **plan** : liste des fichiers, rôle de chacun, ordre. Coder ensuite, une fois validé.
- Les commandes **lecture seule** (lister, lire, `git status`, `git diff`, `--dry-run`) peuvent être lancées sans demander.
- **Une étape à la fois.** Pas de génération massive de tous les modules d'un coup : on avance module par module, vérifiable.
- **Validation du résultat.** Chaque fichier créé ou modifié doit être relisible et validé **avant de passer au suivant**. Si c'est du code, montrer un **extrait clé**. Si c'est un fichier de config, montrer un **exemple d'exécution ou de vérification**.
- En cas d'ambiguïté ou de choix structurant (lib, archi, modèle de données) : **poser la question**, proposer une recommandation, ne pas deviner silencieusement.

---

## 2. Génération de Fichiers & Code

- **Respecter `project-brief.md`** : architecture, conventions de naming, docstrings Google, logging, structure des dossiers.
- **Code typé** (type hints) et **docstrings** sur tout ce qui est public.
- **Logique métier = fonctions pures**, isolées de l'I/O. L'I/O (Odoo, API Claude) reste dans `odoo_client.py` / `ai_generator.py`.
- **Pas de code mort, pas de TODO vagues, pas de sur-ingénierie.** Le POC doit rester lisible et présentable.
- **Commentaires** : expliquer le *pourquoi*, pas le *quoi*. Le code se lit seul ; on commente les décisions métier (seuils de relance, choix de filtre Odoo).
- **Gestion d'erreurs explicite** : échec rapide et message clair (connexion Odoo, variable d'env manquante, erreur API).
- **Pas de secret en dur** (cf. brief §6). Tout passe par `.env`.
- Chaque nouveau module livré avec, si pertinent, un **test minimal** dans `tests/`.

---

## 3. Git Workflow

- **Branches** : on travaille depuis **`dev`**. Toute fonctionnalité part d'une branche créée depuis `dev` (`feat/...`, `fix/...`, `docs/...`, `chore/...`) et y est remergée. `main` reste stable.
- **Commits atomiques** : un commit = un changement cohérent et autonome. Pas de commit fourre-tout.
- **Messages clairs**, à l'impératif, en français, format :
  ```
  <type>: <résumé court à l'impératif>

  <corps optionnel : pourquoi, pas seulement quoi>
  ```
  Types : `feat`, `fix`, `docs`, `chore`, `test`, `refactor`.
  ```
  ✅ BON      : feat: implement fetch_unpaid_invoices pour Odoo
  ✅ BON      : fix: validate .env variables at startup
  ❌ MAUVAIS  : update code
  ❌ MAUVAIS  : feat: implement everything
  ```
- **Commit/push uniquement sur demande explicite.** Ne jamais committer sans validation.
- Montrer `git status` + `git diff` avant de proposer un commit.

---

## 4. Rapporter les Blocages

En cas d'erreur ou de blocage, **rapport structuré** (pas de « ça marche pas ») :

```
🔴 ERREUR    : <message exact / nature du problème>
📍 CONTEXTE  : <fichier, commande, étape où ça survient>
🔍 HYPOTHÈSE : <cause probable>
🛠️ PISTE     : <action proposée pour débloquer>
```

**Exemple concret :**

```
🔴 ERREUR    : ModuleNotFoundError: No module named 'xmlrpc'
📍 CONTEXTE  : python src/main.py, après docker compose up
🔍 HYPOTHÈSE : Mauvais venv ou interpréteur Python ?
🛠️ PISTE     : Vérifier `which python`, `pip list`, refaire le venv si besoin
```

- Toujours coller la **sortie d'erreur réelle**, pas une paraphrase.
- Si plusieurs causes possibles : les lister, classées par probabilité.
- Ne **jamais masquer** un échec ni prétendre qu'une étape a réussi si elle a échoué.
- Si bloqué après 1-2 tentatives raisonnables : **s'arrêter et demander**, ne pas multiplier les essais hasardeux.

---

## 5. Limites Explicites

- ❌ **Pas d'envoi réel** de mail / SMS / courrier. Phase 1 = génération + affichage uniquement.
- ❌ **Pas d'écriture dans Odoo.** Lecture seule sur les factures.
- ❌ **Pas de dépendances exotiques.** Stack figée dans le brief (`anthropic`, `python-dotenv`, stdlib). Tout ajout doit être justifié et validé explicitement.
- ✅ **Docker is king** : Odoo et PostgreSQL tournent en conteneurs. Pas d'install locale d'Odoo ni de Postgres sur la machine hôte. Tout passe par `docker compose`.
- ❌ Pas de déploiement cloud, pas de front web, pas de scheduler en Phase 1.
- ❌ Pas de refactor non demandé ni de réécriture de modules existants sans accord.
- ❌ Pas de secret en clair (code, logs, sortie console, commit).

---

## 6. Checklist par Phase

### Phase A — Setup Odoo (Docker)
- [ ] `docker/docker-compose.yml` : services `odoo:17` + `postgres:15`, volumes, ports (`8069`).
- [ ] `docker compose up` démarre Odoo, accessible sur `http://localhost:8069`.
- [ ] Base créée, module **`account`** installé, données de démo présentes.
- [ ] Présence de factures clients impayées et échues dans la démo (sinon en créer).
- [ ] Script ou données seed préparées dans `docker/fixtures/` ou documentées dans `README.md` pour reproduire la démo rapidement (cf. brief §4 — 6 factures de test).
- [ ] Identifiants Odoo reportés dans `.env` (jamais commités).

### Phase B — Agent Python
- [ ] `requirements.txt` minimal installé dans un venv.
- [ ] `config.py` charge et valide le `.env` (échec clair si variable manquante).
- [ ] `odoo_client.py` : `authenticate()` OK (uid récupéré), `fetch_unpaid_invoices()` renvoie les factures du domaine de filtre.
- [ ] `models.py` : dataclasses `Invoice` / `Customer`.
- [ ] `relance_policy.py` : mapping retard → niveau (1/2/3), avec tests unitaires verts.

### Phase C — Intégration IA
- [ ] `ai_generator.py` : prompt construit à partir d'`Invoice` + niveau, appel Claude OK.
- [ ] Messages générés cohérents avec le **ton** de chaque niveau de relance.
- [ ] Clé API lue depuis `.env`, jamais loggée.
- [ ] `main.py` orchestre : fetch → classify → generate → affichage console (tableau récap + messages).

### Phase D — Test & Démo
- [ ] `pytest` vert sur la logique pure (`relance_policy`, formatage prompt mocké).
- [ ] Run complet de bout en bout sur la démo Odoo, sortie lisible.
- [ ] `README.md` : prérequis, `docker compose up`, config `.env`, commande de lancement.
- [ ] Scénario de démo répétable et présentable en entretien (1-2 commandes).
