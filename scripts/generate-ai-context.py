#!/usr/bin/env python3
"""Génère le fichier de contexte canonique consommé par Claude Code.

Sortie : .claude/skills/project-context.md (régénéré à la demande).

Stack détectée : Python. Le script lit les dépendances de requirements.txt,
liste les fichiers de configuration racine pertinents et l'arborescence du
projet (hors répertoires lourds ou non pertinents).

Usage :
    python scripts/generate-ai-context.py
"""

from __future__ import annotations

import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / ".claude" / "skills" / "project-context.md"

# Répertoires exclus de l'arborescence (imposés par init-ai-workspace + artefacts Python).
EXCLUDE_DIRS = {
    "node_modules", ".git", "dist", "build", ".claude", "coverage",
    ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
}
EXCLUDE_GLOBS = ("*.egg-info",)

# Commande de test déduite des dépendances de développement (pytest).
TEST_COMMAND = "pytest"

# Fichiers de configuration racine pertinents pour une stack Python.
ROOT_CONFIG_CANDIDATES = [
    "pyproject.toml", "setup.cfg", "setup.py", "tox.ini", "pytest.ini",
    "requirements.txt", "requirements-dev.txt", ".env.example",
]


def iter_tree() -> list[str]:
    """Liste récursivement fichiers et dossiers, hors exclusions."""
    entries: list[str] = []

    def walk(directory: Path, prefix: str = "") -> None:
        for path in sorted(directory.iterdir(), key=lambda p: p.name):
            if path.name in EXCLUDE_DIRS or any(path.match(g) for g in EXCLUDE_GLOBS):
                continue
            relative = f"{prefix}{path.name}"
            entries.append(relative)
            if path.is_dir():
                walk(path, relative + "/")

    walk(ROOT)
    return entries


def read_dependencies() -> list[str]:
    """Lit les dépendances déclarées dans requirements.txt."""
    requirements = ROOT / "requirements.txt"
    if not requirements.exists():
        return []
    deps = []
    for line in requirements.read_text(encoding="utf-8").splitlines():
        stripped = line.split("#", 1)[0].strip()
        if stripped and not stripped.startswith("-"):
            deps.append(stripped)
    return deps


def root_config_files() -> list[str]:
    """Retourne les fichiers de configuration racine présents."""
    return [name for name in ROOT_CONFIG_CANDIDATES if (ROOT / name).exists()]


def build_context() -> str:
    """Construit le contenu Markdown du fichier de contexte."""
    deps = read_dependencies()
    configs = root_config_files()
    now = datetime.datetime.now().astimezone()

    lines: list[str] = [
        "# Contexte projet",
        "",
        "> Fichier genere automatiquement par `scripts/generate-ai-context.py`.",
        "> **Ne pas editer a la main** : toute modification sera ecrasee a la prochaine generation.",
        "",
        f"- **Date de generation :** {now:%Y-%m-%d %H:%M:%S %z}",
        "- **Stack detectee :** Python 3.11+",
        f"- **Commande de test :** {TEST_COMMAND}",
        "",
        "## Dependances",
        "",
    ]
    lines += [f"- `{dep}`" for dep in deps] or ["_Aucune dependance dans requirements.txt._"]
    lines += ["", "## Fichiers de configuration racine", ""]
    lines += [f"- `{cfg}`" for cfg in configs] or ["_Aucun fichier de configuration racine reconnu._"]
    lines += ["", "## Arborescence", "", "```", *iter_tree(), "```"]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(build_context(), encoding="utf-8")
    print(f"Contexte genere : {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
