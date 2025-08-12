from __future__ import annotations

import os
import json
import pymysql
from pathlib import Path

from a2a.types import AgentSkill, AgentCard, AgentCapabilities


def _get_db_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        db=os.getenv("DB_NAME", "agent_house"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def _load_agent_record_by_folder() -> dict | None:
    folder_name = Path(__file__).resolve().parent.parent.name
    conn = _get_db_connection()
    try:
        with conn.cursor() as cursor:
            def _snake_to_title(s: str) -> str:
                return " ".join(word.capitalize() for word in s.split("_"))

            title_name = _snake_to_title(folder_name)
            cursor.execute(
                "SELECT * FROM agents WHERE name IN (%s, %s) LIMIT 1",
                (folder_name, title_name),
            )
            return cursor.fetchone()
    finally:
        conn.close()


def build_agent_card(host: str, port: int) -> AgentCard:
    record = _load_agent_record_by_folder()
    if record:
        print(f"[AgentCard] DB record loaded for geocode_agent: {record['name']}")
    else:
        print("[AgentCard] Using static fallback AgentCard for geocode_agent")

    if not record:
        return AgentCard(
            name="Geocode Agent",
            description="도시명 기반으로 위경도 추출 결과를 제공하는 에이전트입니다.",
            url=f"http://{host}:{port}/",
            version="1.0.0",
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            capabilities=AgentCapabilities(streaming=True),
            skills=[
                AgentSkill(
                    id="geocode_agent",
                    name="Geocode Agent",
                    description="도시명 기반으로 위경도 추출 결과를 제공하는 에이전트입니다.",
                    tags=["search"],
                )
            ],
        )

    raw_cap = json.loads(record["capabilities"])

    def _sanitize_cap(cap: dict) -> dict:
        safe = {}
        for k, v in cap.items():
            if k == "streaming":
                safe[k] = bool(v)
            else:
                if isinstance(v, list):
                    safe[k] = v
                elif v:
                    safe[k] = []
        return safe

    capabilities_dict = _sanitize_cap(raw_cap)
    skills_list = json.loads(record["skills"])
    default_input_modes = json.loads(record["default_input_modes"])
    default_output_modes = json.loads(record["default_output_modes"])

    return AgentCard(
        name=record["name"],
        description=record["description"],
        url=f"http://{host}:{port}/",
        version="1.0.0",
        defaultInputModes=default_input_modes,
        defaultOutputModes=default_output_modes,
        capabilities=AgentCapabilities(**capabilities_dict),
        skills=[AgentSkill(**skill) for skill in skills_list],
    )