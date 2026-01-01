"""
도구 기반 클래스 및 레지스트리
"""
from typing import Callable, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ToolDefinition:
    """도구 정의"""
    name: str
    description: str
    func: Callable
    parameters: dict = field(default_factory=dict)
    
    def to_langchain_tool(self):
        """LangChain Tool 형식으로 변환"""
        try:
            from langchain_core.tools import Tool
            return Tool(
                name=self.name,
                description=self.description,
                func=self.func,
            )
        except ImportError:
            raise ImportError("langchain-core 패키지가 필요합니다: pip install langchain-core")


class ToolRegistry:
    """
    도구 레지스트리
    
    에이전트가 사용할 도구들을 등록하고 관리합니다.
    """
    
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}
    
    def register(
        self,
        name: str,
        description: str,
        func: Callable,
        parameters: dict = None
    ) -> "ToolRegistry":
        """
        도구 등록
        
        Args:
            name: 도구 이름
            description: 도구 설명
            func: 실행 함수
            parameters: 파라미터 스키마
        
        Returns:
            self (체이닝용)
        """
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            func=func,
            parameters=parameters or {},
        )
        return self
    
    def register_tool(self, tool: ToolDefinition) -> "ToolRegistry":
        """ToolDefinition 객체로 등록"""
        self._tools[tool.name] = tool
        return self
    
    def get(self, name: str) -> Optional[ToolDefinition]:
        """이름으로 도구 조회"""
        return self._tools.get(name)
    
    def get_tools(self, names: list[str] = None) -> list[ToolDefinition]:
        """
        도구 목록 반환
        
        Args:
            names: 가져올 도구 이름 목록 (None이면 전체)
        
        Returns:
            ToolDefinition 목록
        """
        if names is None:
            return list(self._tools.values())
        return [self._tools[n] for n in names if n in self._tools]
    
    def get_langchain_tools(self, names: list[str] = None) -> list:
        """LangChain Tool 형식으로 반환"""
        tools = self.get_tools(names)
        return [t.to_langchain_tool() for t in tools]
    
    def list_names(self) -> list[str]:
        """등록된 도구 이름 목록"""
        return list(self._tools.keys())
    
    def __contains__(self, name: str) -> bool:
        return name in self._tools
    
    def __len__(self) -> int:
        return len(self._tools)


def create_default_registry() -> ToolRegistry:
    """기본 도구가 등록된 레지스트리 생성"""
    from .file_tools import (
        read_file_tool,
        write_file_tool,
        glob_tool,
        grep_tool,
        list_dir_tool,
    )
    
    registry = ToolRegistry()
    registry.register_tool(read_file_tool)
    registry.register_tool(write_file_tool)
    registry.register_tool(glob_tool)
    registry.register_tool(grep_tool)
    registry.register_tool(list_dir_tool)
    
    return registry
