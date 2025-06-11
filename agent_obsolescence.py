#!/usr/bin/env python
# agent_obsolescence.py – version "in‑memory" 2025‑06
"""
Met à jour les notebooks (.ipynb) **directement en mémoire** : aucune diff,
aucun appel au binaire `patch`.  Pour chaque cellule de code, on détecte les
appels dépréciés et on demande à Mistral de renvoyer **le code corrigé** puis on
ré‑écrit le notebook.
"""

from __future__ import annotations

<<<<<<< HEAD
=======
import ast
>>>>>>> 5194d6b (agent_obs)
import os
import re
import sys
from pathlib import Path
from typing import List, Dict

import nbformat  # pip install nbformat
from langchain_mistralai import ChatMistralAI  # pip install langchain-mistralai mistralai
from langchain.schema import SystemMessage, HumanMessage

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
API_KEY = os.getenv("MISTRAL_API_KEY")
if not API_KEY:
    sys.exit("❌  Variable MISTRAL_API_KEY introuvable ; exporte ta clé.")

REPO_ROOT = Path(os.getenv("CONTENT_REPO", ".")).resolve()
MODEL_NAME = os.getenv("MISTRAL_MODEL", "mistral-small")

# Signatures obsolètes → remplacement suggéré (REGEX keys)
# Next probably check the outcome and based on that we will correct the functions or the import
DEPRECATED_MAP: Dict[str, str] = {
    # Index.format → astype(str)
    r"\.format\(": ".astype(str)(",
    # DataFrame / Series .ix → .loc / .iloc  (cas générique)
    r"DataFrame\.ix": "DataFrame.loc / DataFrame.iloc",
    # Series ravel (ravel()) → to_numpy()
    r"\.ravel\(": ".to_numpy(",
    # Alias de fréquence trimestrielle 'Q' ou "Q" → 'QE'
    r"freq=[\"']Q[\"']": "freq='QE'",
}
# Pré-compile un méga-regex (OR) non échappé, insensible à la casse
PATTERN_RE = re.compile("|".join(DEPRECATED_MAP.keys()), re.IGNORECASE)

<<<<<<< HEAD

=======
FREQ_RE = re.compile(r"""freq\s*=\s*['"]Q['"]""")

def is_valid_python(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False
>>>>>>> 5194d6b (agent_obs)

def list_notebooks(root: Path) -> List[Path]:
    return list(root.rglob("*.ipynb"))


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------
chat = ChatMistralAI(model=MODEL_NAME, temperature=0.0)
SYSTEM_MSG = SystemMessage(
    content=(
        "You are an expert Python instructor. When given a code snippet, "
        "return ONLY a corrected snippet, no markdown fences, no explanations."))


def fix_code_snippet(snippet: str, mapping: Dict[str, str]) -> str:
    """Envoie le code au LLM et récupère la version corrigée."""
    human_content = (
        "Code to fix:\n" + snippet + "\n\n" +
        "Replace any deprecated pattern according to this table (if present):\n" +
        "\n".join([f"- {k} → {v}" for k, v in mapping.items()]))
    resp = chat.invoke([SYSTEM_MSG, HumanMessage(content=human_content)])
    return resp.content.strip()

<<<<<<< HEAD

=======
def safe_fix(snippet: str) -> str:
    """Appelle le LLM, vérifie la syntaxe, fallback regex si besoin."""
    fixed = fix_code_snippet(snippet, DEPRECATED_MAP)
    if is_valid_python(fixed):
        return fixed

    # Fallback 1 : simple regex sur freq='Q'
    regex_fixed = FREQ_RE.sub("freq='QE'", snippet)
    if is_valid_python(regex_fixed):
        return regex_fixed

    # Fallback 2 : retourner le code original
    print("⚠️  Impossible de corriger automatiquement la cellule.")
    return snippet
    
>>>>>>> 5194d6b (agent_obs)
# ---------------------------------------------------------------------------
# PIPELINE PRINCIPAL
# ---------------------------------------------------------------------------

<<<<<<< HEAD
=======

>>>>>>> 5194d6b (agent_obs)
def process_notebook(nb_path: Path) -> bool:
    """Modifie le notebook en place. Retourne True s'il y a eu un changement."""
    nb = nbformat.read(nb_path, as_version=4)
    changed = False

    for cell in nb.cells:
        if cell.cell_type != "code":
            continue
        src: str = cell["source"]
        if not PATTERN_RE.search(src):
            continue  # rien à corriger

        try:
            fixed = fix_code_snippet(src, DEPRECATED_MAP)
        except Exception as e:
            print(f"⚠️  LLM failure on {nb_path.name}: {e}")
            continue

<<<<<<< HEAD
        if fixed and fixed != src:
            cell["source"] = fixed
=======
        new_code = safe_fix(src)
        if new_code != src:
            cell["source"] = new_code
>>>>>>> 5194d6b (agent_obs)
            changed = True
            print(f"→ Patched cell in {nb_path.name} (len {len(src)} -> {len(fixed)})")

    if changed:
        nbformat.write(nb, nb_path)
    return changed


def main() -> None:
    modified_files = []
    for nb in list_notebooks(REPO_ROOT):
        if process_notebook(nb):
            modified_files.append(nb.relative_to(REPO_ROOT))

    if modified_files:
        print("\n🎉  Notebooks mis à jour :")
        for p in modified_files:
            print(f" • {p}")
        print("\n📝  Pense à git add / commit avant push.")
    else:
        print("👍  Aucune mise à jour nécessaire.")


if __name__ == "__main__":
    main()
