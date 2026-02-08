# Skills Package
"""
Skill 모듈 패키지

기존 파서 모듈을 Skill로 래핑하여 Subagent에서 호출 가능하게 합니다.
Mock/Real 스위칭을 지원합니다.
"""

from .skill_interface import BaseSkill, SkillResult
from .skills_registry import SkillsRegistry, get_tools_map

__all__ = [
    "BaseSkill",
    "SkillResult",
    "SkillsRegistry",
    "get_tools_map",
]
