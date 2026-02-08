"""
Skill 레지스트리

Skill 동적 로딩, 등록, Mock/Real 스위칭을 지원합니다.
"""

from typing import Dict, Type, Optional, Any
import logging

from .skill_interface import BaseSkill, MockSkill, SkillResult

logger = logging.getLogger(__name__)


class SkillsRegistry:
    """
    Skill 레지스트리
    
    Skill을 등록하고 이름으로 조회할 수 있습니다.
    Mock/Real 모드 전환을 지원합니다.
    
    Example:
        registry = SkillsRegistry()
        registry.register(ParseProcCodeSkill())
        
        skill = registry.get("parse_proc_code")
        result = skill.invoke(source_code)
    """
    
    def __init__(self, use_mock: bool = False):
        """
        Args:
            use_mock: True이면 Mock Skill 사용
        """
        self._skills: Dict[str, BaseSkill] = {}
        self._mock_skills: Dict[str, BaseSkill] = {}
        self._use_mock = use_mock
    
    def register(self, skill: BaseSkill) -> "SkillsRegistry":
        """
        Skill 등록
        
        Args:
            skill: 등록할 Skill 인스턴스
            
        Returns:
            self (체이닝용)
        """
        self._skills[skill.name] = skill
        logger.debug(f"Skill 등록: {skill.name}")
        return self
    
    def register_mock(self, name: str, mock_response: Dict[str, Any]) -> "SkillsRegistry":
        """
        Mock Skill 등록
        
        Args:
            name: Skill 이름
            mock_response: Mock 응답 데이터
            
        Returns:
            self (체이닝용)
        """
        self._mock_skills[name] = MockSkill(name, mock_response)
        logger.debug(f"Mock Skill 등록: {name}")
        return self
    
    def get(self, name: str) -> Optional[BaseSkill]:
        """
        Skill 조회
        
        Args:
            name: Skill 이름
            
        Returns:
            Skill 인스턴스 (없으면 None)
        """
        if self._use_mock and name in self._mock_skills:
            return self._mock_skills[name]
        return self._skills.get(name)
    
    def set_mock_mode(self, use_mock: bool) -> None:
        """Mock 모드 설정"""
        self._use_mock = use_mock
        logger.info(f"Mock 모드: {'ON' if use_mock else 'OFF'}")
    
    def list_skills(self) -> list[str]:
        """등록된 Skill 이름 목록"""
        return list(self._skills.keys())
    
    def list_mock_skills(self) -> list[str]:
        """등록된 Mock Skill 이름 목록"""
        return list(self._mock_skills.keys())


# 글로벌 레지스트리 인스턴스
_registry: Optional[SkillsRegistry] = None


def get_registry(use_mock: bool = False) -> SkillsRegistry:
    """
    글로벌 레지스트리 가져오기 (싱글톤)
    
    Args:
        use_mock: Mock 모드 사용 여부
        
    Returns:
        SkillsRegistry 인스턴스
    """
    global _registry
    if _registry is None:
        _registry = SkillsRegistry(use_mock=use_mock)
        _load_default_skills(_registry)
    return _registry


def get_tools_map(use_mock: bool = False) -> Dict[str, BaseSkill]:
    """
    tools_map 딕셔너리 반환 (호환성용)
    
    노드에서 tools_map["skill_name"].invoke() 형태로 사용할 수 있습니다.
    
    Args:
        use_mock: Mock 모드 사용 여부
        
    Returns:
        {skill_name: skill_instance} 딕셔너리
    """
    registry = get_registry(use_mock)
    return {name: registry.get(name) for name in registry.list_skills()}


def _load_default_skills(registry: SkillsRegistry) -> None:
    """기본 Skill 로딩"""
    try:
        from .parse_proc_code import ParseProcCodeSkill
        registry.register(ParseProcCodeSkill())
    except ImportError as e:
        logger.warning(f"ParseProcCodeSkill 로딩 실패: {e}")
    
    try:
        from .validate_ast import ValidateAstSkill
        registry.register(ValidateAstSkill())
    except ImportError as e:
        logger.warning(f"ValidateAstSkill 로딩 실패: {e}")
    
    try:
        from .convert_sql_draft import ConvertSqlDraftSkill
        registry.register(ConvertSqlDraftSkill())
    except ImportError as e:
        logger.warning(f"ConvertSqlDraftSkill 로딩 실패: {e}")
    
    # 기본 Mock 데이터 등록
    _register_default_mocks(registry)


def _register_default_mocks(registry: SkillsRegistry) -> None:
    """기본 Mock 데이터 등록"""
    registry.register_mock("parse_proc_code", {
        "headers": ["stdio.h", "stdlib.h"],
        "host_vars": [
            {"name": "order_id", "type": "int"},
            {"name": "customer_name", "type": "char[50]"},
        ],
        "sql_blocks": [
            {"id": "select_0", "content": "SELECT * FROM orders WHERE id = :order_id", "type": "select"},
        ],
        "functions": [
            {"name": "process_order", "return_type": "int", "params": ["ORDER_INFO* info"]},
        ],
    })
    
    registry.register_mock("validate_ast", [])  # 에러 없음
    
    registry.register_mock("convert_sql_draft", {
        "id": "select_0",
        "xml": '<select id="select_0" resultType="map">SELECT * FROM orders WHERE id = #{orderId}</select>',
        "confidence": "high",
    })
