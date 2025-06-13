#!/usr/bin/env python
# agent_obsolescence_dynamic.py – 2025‑06‑12 (debug v2)

from __future__ import annotations

import os
import sys
import warnings
import ast
from pathlib import Path
from typing import List

import nbformat
from nbclient import NotebookClient
from langchain_mistralai import ChatMistralAI
from langchain.schema import SystemMessage, HumanMessage

# ---------------------------------------------------------------------------
# CONFIGURATION GLOBALE
# ---------------------------------------------------------------------------

os.environ.setdefault("PYTHONWARNINGS", "always")

API_KEY = os.getenv("MISTRAL_API_KEY")
if not API_KEY:
    sys.exit("❌  MISTRAL_API_KEY missing. export it then retry.")

REPO_ROOT = Path(os.getenv("CONTENT_REPO", ".")).resolve()
MODEL_NAME = os.getenv("MISTRAL_MODEL", "mistral-small")
EXEC_TIMEOUT = int(os.getenv("EXEC_TIMEOUT", "120"))  # sec/notebook

chat = ChatMistralAI(model=MODEL_NAME, temperature=0.0)
SYS_MSG = SystemMessage(
    content=(
        "You are an expert Python mentor. Given a warning message and the exact "
        "code that triggers it, return ONLY the fixed code. No markdown, no extra words."))

# ---------------------------------------------------------------------------
# FONCTIONS UTILES
# ---------------------------------------------------------------------------

def execute_and_collect(nb_path: Path) -> List[warnings.WarningMessage]:
    """Exécute un notebook et renvoie la liste des warnings capturés."""
    nb = nbformat.read(nb_path, as_version=4)
    with warnings.catch_warnings(record=True) as w:
        warnings.filterwarnings("always", category=FutureWarning)
        warnings.filterwarnings("always", category=DeprecationWarning)
        try:
            NotebookClient(nb, timeout=EXEC_TIMEOUT, allow_errors=True).execute()
        except Exception as exc:
            print(f"⚠️  Execution error in {nb_path.name}: {exc}")
        return list(w)


def code_needs_fix(code: str, warn_msg: str) -> bool:
    """Heuristique : au moins un token du warning présent dans la cellule."""
    tokens = [t.strip("',.()[]\n ") for t in warn_msg.split() if len(t) > 3]
    return any(tok in code for tok in tokens)


def llm_fix(code: str, warn_msg: str) -> str:
    prompt = HumanMessage(
        content=(
            f"Warning message:\n{warn_msg}\n\nProblematic code:\n" + code + "\n\nCorrect it."))
    return chat.invoke([SYS_MSG, prompt]).content.strip()


def is_valid_py(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False

# ---------------------------------------------------------------------------
# TRAITEMENT NOTEBOOK
# ---------------------------------------------------------------------------

def process_notebook(nb_path: Path) -> bool:
    warnings_list = execute_and_collect(nb_path)
    print(f"{nb_path.name} → warnings capturés : {len(warnings_list)}")
    for w in warnings_list:
        print("   •", w.message)

    if not warnings_list:
        return False

    nb = nbformat.read(nb_path, as_version=4)
    modified = False

    for w in warnings_list:
        warn_msg = str(w.message)
        if not ("deprecated" in warn_msg.lower() or "futurewarning" in warn_msg.lower()):
            continue

        for cell in nb.cells:
            if cell.cell_type != "code":
                continue
            src = cell["source"]
            if not code_needs_fix(src, warn_msg):
                continue

            fixed = llm_fix(src, warn_msg)
            if fixed and fixed != src and is_valid_py(fixed):
                cell["source"] = fixed
                modified = True
                print(f"→ Cell fixed in {nb_path.name} for warning: {warn_msg[:60]}…")
                break  # passe au warning suivant

    if modified:
        nbformat.write(nb, nb_path)
    return modified

# ---------------------------------------------------------------------------
# MAIN ENTRY
# ---------------------------------------------------------------------------

def main() -> None:
    changed = []
    for nb in REPO_ROOT.rglob("*.ipynb"):
        if process_notebook(nb):
            changed.append(nb.relative_to(REPO_ROOT))

    if changed:
        print("\n🎉 Notebooks updated:")
        for p in changed:
            print(" •", p)
        print("Push these commits when ready.")
    else:
        print("👍  No deprecation warnings found across notebooks.")


if __name__ == "__main__":
    main()
