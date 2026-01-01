"""
메인 오케스트레이터

동적(Dynamic) 및 정적(Static) 오케스트레이션 모드를 통합 지원합니다.
"""
from typing import Any, Optional

from .config import LLMConfig, OrchestratorConfig, AgentSystemConfig
from .memory import EpisodicMemory
from .agents.base import AgentConfig, AGENT_CONFIGS
from .tools.base import ToolRegistry, create_default_registry


class LangChainOrchestrator:
    """
    LangGraph 기반 멀티 에이전트 오케스트레이터
    
    두 가지 모드 지원:
    - Dynamic: Reflection + Self-Evolve 기반 동적 오케스트레이션
    - Static: 미리 정의된 워크플로우 기반 실행
    
    사용 예시:
    ```python
    # 동적 모드
    orch = LangChainOrchestrator(mode="dynamic")
    result = orch.run("Pro*C 파일 변환", context={"target_dir": "./src"})
    
    # 정적 모드
    from lang_chain_agents import PROC_TO_JAVA_WORKFLOW
    orch = LangChainOrchestrator(mode="static")
    orch.set_workflow(PROC_TO_JAVA_WORKFLOW)
    result = orch.run("Pro*C 파일 변환", context={"target_dir": "./src"})
    ```
    """
    
    def __init__(
        self,
        mode: str = "dynamic",
        config: Optional[AgentSystemConfig] = None,
        llm_config: Optional[LLMConfig] = None,
    ):
        """
        Args:
            mode: "dynamic" 또는 "static"
            config: 전체 시스템 설정
            llm_config: LLM 설정 (config와 함께 사용 시 무시됨)
        """
        self.mode = mode
        
        # 설정 초기화
        if config:
            self.config = config
        else:
            self.config = AgentSystemConfig(
                llm=llm_config or LLMConfig.from_env(),
                orchestrator=OrchestratorConfig(mode=mode),
            )
        
        # LLM 초기화
        self._llm = None
        
        # 에이전트 등록
        self.agents: dict[str, AgentConfig] = {}
        
        # 도구 레지스트리
        self.tool_registry = create_default_registry()
        
        # 메모리 (동적 모드용)
        self.memory = EpisodicMemory(
            max_episodes=self.config.orchestrator.memory_max_episodes
        )
        
        # 워크플로우 (정적 모드용)
        self._workflow = None
        
        # 컴파일된 그래프
        self._graph = None
        
        # 기본 에이전트 로드
        self._load_default_agents()
    
    def _load_default_agents(self):
        """기본 7개 에이전트 로드"""
        for name, config in AGENT_CONFIGS.items():
            self.agents[name] = config
    
    def _get_llm(self):
        """LLM 인스턴스 가져오기 (지연 초기화)"""
        if self._llm is None:
            try:
                from langchain_openai import ChatOpenAI
            except ImportError:
                raise ImportError(
                    "langchain-openai 패키지가 필요합니다: pip install langchain-openai"
                )
            
            self._llm = ChatOpenAI(**self.config.llm.to_dict())
        
        return self._llm
    
    def register_agent(self, config: AgentConfig) -> "LangChainOrchestrator":
        """
        에이전트 등록
        
        Args:
            config: AgentConfig 인스턴스
        
        Returns:
            self (체이닝용)
        """
        self.agents[config.name] = config
        self._graph = None  # 그래프 재빌드 필요
        return self
    
    def register_tool(self, name: str, description: str, func: Any) -> "LangChainOrchestrator":
        """
        도구 등록
        
        Args:
            name: 도구 이름
            description: 도구 설명
            func: 실행 함수
        
        Returns:
            self (체이닝용)
        """
        self.tool_registry.register(name, description, func)
        self._graph = None
        return self
    
    def set_workflow(self, workflow) -> "LangChainOrchestrator":
        """
        워크플로우 설정 (정적 모드용)
        
        Args:
            workflow: BaseWorkflow 인스턴스
        
        Returns:
            self (체이닝용)
        """
        self._workflow = workflow
        self._graph = None
        return self
    
    def set_mode(self, mode: str) -> "LangChainOrchestrator":
        """
        오케스트레이션 모드 변경
        
        Args:
            mode: "dynamic" 또는 "static"
        """
        self.mode = mode
        self.config.orchestrator.mode = mode
        self._graph = None
        return self
    
    def build(self) -> "LangChainOrchestrator":
        """그래프 빌드"""
        llm = self._get_llm()
        
        if self.mode == "dynamic":
            from .orchestration.manager import DynamicManager
            
            manager = DynamicManager(
                agents=self.agents,
                llm=llm,
                tool_registry=self.tool_registry,
                memory=self.memory,
                max_iterations=self.config.orchestrator.max_iterations,
            )
            self._graph = manager.build_graph()
            
        else:  # static
            if not self._workflow:
                from .workflows.proc_to_java import PROC_TO_JAVA_WORKFLOW
                self._workflow = PROC_TO_JAVA_WORKFLOW
            
            self._graph = self._workflow.build_graph(
                self.agents, llm, self.tool_registry
            )
        
        return self
    
    def run(
        self,
        task: str,
        context: dict = None,
        thread_id: str = "default"
    ) -> dict:
        """
        오케스트레이션 실행
        
        Args:
            task: 사용자 작업 요청
            context: 변환 컨텍스트 (target_dir, output_dir 등)
            thread_id: 체크포인트용 스레드 ID
        
        Returns:
            최종 상태 딕셔너리
        """
        if not self._graph:
            self.build()
        
        from .state import create_initial_state
        
        initial_state = create_initial_state(task, context, mode=self.mode)
        config = {"configurable": {"thread_id": thread_id}}
        
        return self._graph.invoke(initial_state, config)
    
    async def arun(
        self,
        task: str,
        context: dict = None,
        thread_id: str = "default"
    ) -> dict:
        """비동기 실행"""
        if not self._graph:
            self.build()
        
        from .state import create_initial_state
        
        initial_state = create_initial_state(task, context, mode=self.mode)
        config = {"configurable": {"thread_id": thread_id}}
        
        return await self._graph.ainvoke(initial_state, config)
    
    def list_agents(self) -> list[dict]:
        """등록된 에이전트 목록"""
        return [
            {"name": name, "description": config.description}
            for name, config in self.agents.items()
        ]
    
    def list_tools(self) -> list[str]:
        """등록된 도구 목록"""
        return self.tool_registry.list_names()
    
    def get_memory_stats(self) -> dict:
        """메모리 통계 (동적 모드)"""
        return self.memory.get_statistics()
    
    def clear_memory(self):
        """메모리 초기화"""
        self.memory.clear()
    
    def save_memory(self, path: str):
        """메모리 저장"""
        self.memory.persist_path = path
        self.memory._save()
    
    def load_memory(self, path: str):
        """메모리 로드"""
        self.memory.persist_path = path
        self.memory._load()
