"""
LLM 및 시스템 설정 관리
"""
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMConfig:
    """LLM API 설정"""
    
    model: str = "gpt-4"
    temperature: float = 0.1
    max_tokens: int = 4096
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout: int = 60
    
    @classmethod
    def from_env(cls) -> "LLMConfig":
        """환경 변수에서 설정 로드"""
        return cls(
            model=os.getenv("LLM_MODEL", "gpt-4"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
            api_key=os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("LLM_API_ENDPOINT") or os.getenv("OPENAI_API_BASE"),
            timeout=int(os.getenv("LLM_TIMEOUT", "60")),
        )
    
    def to_dict(self) -> dict:
        """LangChain ChatOpenAI 호환 딕셔너리 반환"""
        config = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
        }
        if self.api_key:
            config["api_key"] = self.api_key
        if self.base_url:
            config["base_url"] = self.base_url
        return config


@dataclass
class OrchestratorConfig:
    """오케스트레이터 설정"""
    
    # 오케스트레이션 모드: "dynamic" 또는 "static"
    mode: str = "dynamic"
    
    # 동적 모드 설정
    max_iterations: int = 10
    reflection_enabled: bool = True
    self_evolve_enabled: bool = True
    
    # 정적 모드 설정
    fail_fast: bool = True
    parallel_enabled: bool = True
    max_parallel: int = 5
    
    # 공통 설정
    checkpoint_enabled: bool = True
    memory_max_episodes: int = 100
    
    @classmethod
    def dynamic(cls, **kwargs) -> "OrchestratorConfig":
        """동적 오케스트레이션 모드로 생성"""
        return cls(mode="dynamic", **kwargs)
    
    @classmethod
    def static(cls, **kwargs) -> "OrchestratorConfig":
        """정적 워크플로우 모드로 생성"""
        return cls(mode="static", **kwargs)


@dataclass
class AgentSystemConfig:
    """전체 시스템 설정"""
    
    llm: LLMConfig = field(default_factory=LLMConfig.from_env)
    orchestrator: OrchestratorConfig = field(default_factory=OrchestratorConfig)
    
    # 아티팩트 저장 경로
    artifacts_dir: str = ".workflow_artifacts"
    
    # 에이전트 정의 경로
    agents_dir: str = ".agents"
