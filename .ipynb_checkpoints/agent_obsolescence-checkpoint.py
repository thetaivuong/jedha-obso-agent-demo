#!/usr/bin/env python
# agent_obsolescence.py
"""
Agent anti-obsolescence Jedha — version PoC
• Scanne tous les .ipynb du dépôt
• Détecte les appels dépréciés listés dans DEPRECATED_MAP
• Demande à Mistral un patch (diff unifié) pour les remplacer
• Applique le patch sur le repo local
"""
import os
import subprocess
import sys
import re, textwrap, pathlib
from pathlib import Path
from typing import List, Dict

import nbformat
from langchain_mistralai import ChatMistralAI
from langchain.schema import SystemMessage, HumanMessage


# :::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
# 1. CONFIGURATION GÉNÉRALE
# :::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
#: clé API lue dans les variables d'environnement (export MISTRAL_API_KEY=...)
API_KEY = os.getenv("MISTRAL_API_KEY")
if not API_KEY:
    sys.exit("❌  MISTRAL_API_KEY absent ; exporte ta clé avant de lancer le script.")

#: racine du dépôt (modifiable, ex: Path("content"))
REPO_ROOT = Path(os.getenv("CONTENT_REPO", ".")).resolve()

#: signatures obsolètes → suggestions
DEPRECATED_MAP: Dict[str, str] = {
    # vues ensemble
    "DataFrame.ix": "DataFrame.loc / DataFrame.iloc",
    "Series.ravel(": "Series.to_numpy()  # ravel déprécié",
    "freq='Q'": "freq='QE'",                 # alias de fréquence trimestrielle
    ".format(": ".astype(str)(",
    # ajoute tes propres patterns ci-dessous
}


# :::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
# 2. OUTILS
# :::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
def list_notebooks(root: Path) -> List[Path]:
    """Retourne tous les .ipynb sous la racine."""
    return list(root.rglob("*.ipynb"))


def extract_code_cells(nb_path: Path) -> List[str]:
    """Renvoie le contenu brut de chaque cellule de code d'un notebook."""
    nb = nbformat.read(nb_path, as_version=4)
    return [c["source"] for c in nb.cells if c.cell_type == "code"]


def scan_cell(cell_src: str) -> List[Dict[str, str]]:
    """
    Cherche les signatures obsolètes dans une cellule.
    Retourne une liste de dicts {bad: ..., suggest: ...}.
    """
    issues = []
    for bad, good in DEPRECATED_MAP.items():
        if bad in cell_src:
            issues.append({"bad": bad, "suggest": good})
    return issues


def build_prompt(file_path: str, snippet: str, issues: List[Dict[str, str]]) -> List:
    """Construit le prompt (messages) pour Mistral."""
    system = SystemMessage(
        content=(
            "Return *only* a valid UNIX unified diff (starting with '---' and '+++'). "
            "No commentary, no Markdown, no triple backticks. "
            "Target file path must match exactly."
        )
    )

    # mini tableau des remplacements pour le LLM
    mapping = "\n".join([f"- {i['bad']}  →  {i['suggest']}" for i in issues])

    user_msg = HumanMessage(
        content=(
            f"File: {file_path}\n\n"
            f"Deprecated mapping:\n{mapping}\n\n"
            f"Problematic snippet:\n```\n{snippet}\n```\n\n"
            "Produce the patch now."
        )
    )
    return [system, user_msg]


def call_llm(messages) -> str:
    """Appelle Mistral et renvoie le diff brut."""
    chat = ChatMistralAI(
        model="mistral-small",  # ←⇢ 'mistral-large' en prod
        temperature=0.0,
        # La clé est lue dans l'env, pas besoin de la passer
    )
    resp = chat.invoke(messages)
    return resp.content.strip()


def apply_patch(diff_text: str) -> None:
    """Applique un diff unifié sur le repo courant via l'outil `patch`."""
    if not diff_text.startswith("---"):
        print("— le diff retourné ne semble pas valide, ignoré.")
        return

    try:
        subprocess.run(
            ["patch", "-p1", "--forward"],
            input=diff_text.encode(),
            check=True,
            capture_output=True,
        )
        print("✅  Patch appliqué.")
    except subprocess.CalledProcessError as e:
        print("⚠️  Patch non appliqué :", e.stderr.decode()[:200])

def sanitize_diff(raw: str, file_rel: str) -> str:
    """
    • Supprime ``` diff, ``` etc.
    • Tronque tout avant la 1ʳᵉ ligne '---'
    • Remplace le chemin absolu par le chemin relatif attendu
    """
    # 1) retire bloc markdown
    cleaned = re.sub(r"```[a-z]*\s*", "", raw, flags=re.I).replace("```", "").strip()
    # 2) garde à partir de la 1ʳᵉ '---'
    start = cleaned.find("---")
    cleaned = cleaned[start:] if start != -1 else cleaned
    # 3) remplace chemin par 'a/<file_rel>' / 'b/<file_rel>'
    cleaned = re.sub(r"--- .*?\n", f"--- a/{file_rel}\n", cleaned, count=1)
    cleaned = re.sub(r"\+\+\+ .*?\n", f"+++ b/{file_rel}\n", cleaned, count=1)
    return textwrap.dedent(cleaned)

# :::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
# 3. PIPELINE PRINCIPAL
# :::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
def main() -> None:
    modified = False

    for nb_path in list_notebooks(REPO_ROOT):
        code_cells = extract_code_cells(nb_path)
        for cell_src in code_cells:
            issues = scan_cell(cell_src)
            if not issues:
                continue  # rien d'obsolète dans cette cellule

            prompt_msgs = build_prompt(str(nb_path), cell_src, issues)
            rel_path = nb_path.relative_to(REPO_ROOT).as_posix()
            raw = call_llm(prompt_msgs)
            diff = sanitize_diff(raw, rel_path)
            apply_patch(diff)
            print("--------- RAW LLM OUTPUT ----------")
            print(diff)
            print("-----------------------------------")
            apply_patch(diff)

            modified = True
            
    if diff.startswith("---"):
        apply_patch(diff)
    else:
        print("Diff vide ou mal formé, ignoré.")

    if modified:
        print("🎉  Des patches ont été appliqués ; committe-les !")
    else:
        print("👍  Aucun appel obsolète trouvé.")


if __name__ == "__main__":
    main()
