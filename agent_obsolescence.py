"""
agent_obsolescence.py  –  Template v0.1
---------------------------------------
Detects deprecated imports/functions in Jedha content notebooks and opens an
automatic Pull‑Request with updated code.

This is a minimal, self‑contained PoC.  Adapt paths, constants and GitHub
integration to your environment.
"""

from __future__ import annotations

import os
import json
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Any

import nbformat  # pip install nbformat
import libcst as cst  # pip install libcst
from langchain_mistralai import ChatMistralAI  # pip install langchain>=0.1.0
from langchain.schema import SystemMessage, HumanMessage
from langchain.prompts import ChatPromptTemplate

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

MISTRAL_API_KEY  = os.getenv("MISTRAL_API_KEY ", "")  # export before running
REPO_ROOT = Path(os.getenv("CONTENT_REPO", ".")).resolve()

# Map a deprecated pattern → modern replacement (extend as needed)
DEPRECATED_MAP: Dict[str, str] = {
    "DataFrame.ix": "DataFrame.loc / DataFrame.iloc",
    "pandas.Panel": "xarray.Dataset ou MultiIndex DataFrame",
    "sklearn.model_selection.cross_val_score": "sklearn.model_selection.cross_validate",
}

# ---------------------------------------------------------------------------
# SCANNER – extract code cells from notebooks
# ---------------------------------------------------------------------------

class NotebookScanner:
    def __init__(self, root: Path):
        self.root = root

    def notebooks(self) -> List[Path]:
        return list(self.root.rglob("*.ipynb"))

    @staticmethod
    def extract_code_cells(nb_path: Path) -> List[str]:
        nb = nbformat.read(nb_path, as_version=4)
        return [c["source"] for c in nb.cells if c.cell_type == "code"]

# ---------------------------------------------------------------------------
# INSPECTOR – detect deprecated patterns in a code string
# ---------------------------------------------------------------------------

class DeprecatedInspector:
    def __init__(self, patterns: Dict[str, str]):
        self.patterns = patterns

    def scan(self, code: str) -> List[Dict[str, str]]:
        issues = []
        for bad, good in self.patterns.items():
            if bad in code:
                issues.append({"bad": bad, "suggest": good})
        return issues

# ---------------------------------------------------------------------------
# PATCH GENERATOR – ask the LLM for a unified diff patch
# ---------------------------------------------------------------------------

class PatchGenerator:
    def __init__(self, model_name: str = "mistral-large", temperature: temperature):
        self.llm = ChatMistralAI(model="mistral-small", temperature=temperature)

    def propose_patch(self, file_path: str, code: str, issues: List[Dict[str, str]]) -> str:
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="You are a senior Python maintainer generating minimal, clean patches."),
            HumanMessage(
                content=(
                    f"FILE: {file_path}\n\n"
                    f"Below is a code excerpt containing deprecated patterns: {json.dumps(issues, indent=2)}\n\n"
                    "Return ONLY a unified diff ("""--- a/*** +++ b/***""" style) that replaces the deprecated calls with modern equivalents.\n"
                    "Do not add comments outside the diff."),
            ),
        ])
        response = self.llm(prompt)
        return response.content.strip()

# ---------------------------------------------------------------------------
# UTILS – apply patch and log result
# ---------------------------------------------------------------------------

def apply_patch(diff: str):
    if not diff:
        return
    proc = subprocess.run(["patch", "-p1", "--forward"], input=diff.encode(), text=False)
    if proc.returncode != 0:
        logging.warning("⚠️  Patch failed – manual review required.")

# ---------------------------------------------------------------------------
# MAIN PIPELINE
# ---------------------------------------------------------------------------

def main() -> None:
    scanner = NotebookScanner(REPO_ROOT)
    inspector = DeprecatedInspector(DEPRECATED_MAP)
    patcher = PatchGenerator()

    for nb_path in scanner.notebooks():
        for cell_code in scanner.extract_code_cells(nb_path):
            issues = inspector.scan(cell_code)
            if issues:
                diff = patcher.propose_patch(str(nb_path), cell_code, issues)
                apply_patch(diff)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    main()

# ---------------------------------------------------------------------------
# 📄 GitHub Actions snippet (save under .github/workflows/agent-obsolescence.yml)
# ---------------------------------------------------------------------------
"""
name: Agent-Obsolescence

on:
  push:
    paths: ['**.ipynb']
  schedule:
    - cron: '0 3 * * 1'   # chaque lundi 03:00 UTC

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install nbformat libcst langchain openai
      - run: python agent_obsolescence.py
      - name: Create PR if changes
        run: |
          git config user.name 'jedha-bot'
          git config user.email 'bot@jedha.com'
          if [ -n "$(git status --porcelain)" ]; then
            git checkout -b bot/auto-update || git checkout bot/auto-update
            git add .
            git commit -m 'auto: update deprecated code'
            git push origin bot/auto-update --force
          fi
"""
