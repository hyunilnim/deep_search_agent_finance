from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime

@dataclass
class AgentInstruction:
    """에이전트 instruction 모델"""
    agent_id: int
    instruction_content: str
    is_active: bool
    instruction_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class AgentCard:
    """에이전트 카드 모델"""
    agent_id: int
    name: str
    description: str
    base_url: str
    version: str
    capabilities: str
    skills: str
    default_input_modes: str
    default_output_modes: str
    is_active: bool
    is_orchestrator: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class AgentUrl:
    """에이전트 URL 모델"""
    base_url: str
    agent_id: int

@dataclass
class CacheInfo:
    """캐시 정보 모델"""
    total_items: int
    valid_items: int
    expired_items: int
    keys: List[str]
    default_duration: int 