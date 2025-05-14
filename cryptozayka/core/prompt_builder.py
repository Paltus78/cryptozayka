"""Build user prompt taking into account scamlist matches."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Dict

SCAMLIST_PATH = Path("memory/scamlist.json")

def _load_scamlist() -> Dict[str, list]:
    if SCAMLIST_PATH.exists():
        return json.loads(SCAMLIST_PATH.read_text())
    return {"scams": []}

def check_against_scamlist(project_name: str) -> List[dict]:
    data = _load_scamlist()
    matches = []
    for scam in data.get("scams", []):
        if scam.get("name", "").lower() in project_name.lower():
            matches.append(scam)
    return matches

def build_project_prompt(name: str, description: str) -> tuple[str, list]:
    matches = check_against_scamlist(name)
    match_text = ""
    if matches:
        match_text = f"⚠️ Обнаружены совпадения с базой скама: {[m['name'] for m in matches]}\n"

    prompt = f"""Проект: {name}
Описание: {description}
{match_text}

Оцени этот airdrop-проект по вероятности скама, полезности и перспективам участия.
Дай краткую рекомендацию: участвовать или нет, с указанием риска."""
    return prompt.strip(), matches
