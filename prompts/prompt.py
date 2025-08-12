from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from shared.database.connection import db_manager
from shared.database.cache_manager import cache_manager
from shared.database.queries import DatabaseQueries


# ---------------------------------------------------------------------------
# DB helpers


def _snake_to_title(s: str) -> str:
    return " ".join(w.capitalize() for w in s.split("_"))


async def _load_prompt_from_db(app_name: str = "default-app") -> str | None:
    """DB에서 instruction 조회 (캐싱 적용)"""
    folder_name = Path(__file__).resolve().parent.parent.name  # geocode_agent
    title_name = _snake_to_title(folder_name)
    
    async def fetch_instruction():
        result = db_manager.execute_sync_query(
            DatabaseQueries.GET_AGENT_INSTRUCTION, 
            (folder_name, title_name, str(app_name))
        )
        return result[0]["instruction_content"] if result else None
    
    return await cache_manager.get_or_fetch(
        key=f"instruction:{folder_name}:{app_name}",
        fetch_func=fetch_instruction,
        cache_duration=600
    )

# Public API
async def get_system_instruction(app_name: str = "default-app") -> str:
    """Always fetch latest prompt; fall back to template with current agent list"""
    prompt = None
    try:
        prompt = await _load_prompt_from_db(app_name)
    except Exception as e:
        print(f"[Prompt][Error] DB fetch failed: {e}")

    return prompt
