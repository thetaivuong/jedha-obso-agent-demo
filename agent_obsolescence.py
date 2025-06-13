#!/usr/bin/env python
# agent_obsolescence.py – version "in‑memory" 2025‑06

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path
from typing import List, Dict

import nbformat 
from langchain_mistralai import ChatMistralAI  
from langchain.schema import SystemMessage, HumanMessage

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

API_KEY = os.getenv("MISTRAL_API_KEY")
if not API_KEY:
    sys.exit("❌  Variable MISTRAL_API_KEY introuvable ; exporte ta clé.")

REPO_ROOT = Path(os.getenv("CONTENT_REPO", ".")).resolve()
MODEL_NAME = os.getenv("MISTRAL_MODEL", "mistral-small")

# Signatures obsolètes
DEPRECATED_MAP: Dict[str, str] = {
    r"\.format\(": ".astype(str)(",
    r"DataFrame\.ix": "DataFrame.loc / DataFrame.iloc",
      r"\.ravel\(": ".to_numpy(",
    r"freq=[\"']Q[\"']": "freq='QE'",
}
# Pré-compile 
PATTERN_RE = re.compile("|".join(DEPRECATED_MAP.keys()), re.IGNORECASE)
FREQ_RE = re.compile(r"""freq\s*=\s*['"]Q['"]""")

def is_valid_python(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False

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
    
# ---------------------------------------------------------------------------
# PIPELINE PRINCIPAL
# ---------------------------------------------------------------------------

def process_notebook(nb_path: Path) -> bool:
    """Modifie le notebook en place. Retourne True s'il y a eu un changement."""
    nb = nbformat.read(nb_path, as_version=4)
    changed = False

    for cell in nb.cells:
        if cell.cell_type != "code":
            continue
        src: str = cell["source"]
        if not PATTERN_RE.search(src):
            continue  

        try:
            fixed = fix_code_snippet(src, DEPRECATED_MAP)
        except Exception as e:
            print(f"⚠️  LLM failure on {nb_path.name}: {e}")
            continue
            
        if fixed and fixed != src:
            cell["source"] = fixed
            
        new_code = safe_fix(src)
        if new_code != src:
            cell["source"] = new_code
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
