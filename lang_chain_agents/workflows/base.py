"""
정적 워크플로우 기반 클래스

미리 정의된 DAG 기반 워크플로우를 실행합니다.
"""
from dataclasses import dataclass, field
from typing import Optional, Any, Callable


@dataclass
class WorkflowStep:
    """워크플로우 단계 정의"""
    
    name: str                           # 단계 이름
    agent: str                          # 실행할 에이전트
    task_template: str                  # 작업 템플릿 (변수 치환 가능)
    
    # 흐름 제어
    next_step: Optional[str] = None     # 다음 단계 (None이면 종료)
    on_failure: Optional[str] = None    # 실패 시 이동할 단계
    
    # 옵션
    retry: int = 0                      # 재시도 횟수
    timeout: int = 300                  # 타임아웃 (초)
    quality_gate: Optional[str] = None  # 품질 게이트 에이전트
    checkpoint: bool = False            # 체크포인트 저장 여부
    
    def get_task(self, context: dict) -> str:
        """컨텍스트로 템플릿 변환"""
        task = self.task_template
        for key, value in context.items():
            task = task.replace(f"${{{key}}}", str(value))
        return task


@dataclass
class ParallelGroup:
    """병렬 실행 그룹"""
    
    name: str
    steps: list[str]                    # 병렬 실행할 단계 이름들
    wait_all: bool = True               # 모든 단계 완료 대기
    fail_fast: bool = False             # 하나 실패 시 전체 중단
    on_success: Optional[str] = None    # 성공 시 다음 단계


@dataclass
class BaseWorkflow:
    """
    정적 워크플로우 기반 클래스
    
    미리 정의된 단계들을 순차/병렬로 실행합니다.
    """
    
    name: str
    description: str = ""
    steps: list[WorkflowStep] = field(default_factory=list)
    parallel_groups: list[ParallelGroup] = field(default_factory=list)
    
    # 워크플로우 설정
    fail_fast: bool = True              # 실패 시 중단
    checkpoint_all: bool = False        # 모든 단계 체크포인트
    
    def add_step(
        self,
        name: str,
        agent: str,
        task: str,
        next_step: str = None,
        **kwargs
    ) -> "BaseWorkflow":
        """단계 추가 (체이닝 지원)"""
        self.steps.append(WorkflowStep(
            name=name,
            agent=agent,
            task_template=task,
            next_step=next_step,
            **kwargs
        ))
        return self
    
    def add_parallel_group(
        self,
        name: str,
        steps: list[str],
        on_success: str = None
    ) -> "BaseWorkflow":
        """병렬 그룹 추가"""
        self.parallel_groups.append(ParallelGroup(
            name=name,
            steps=steps,
            on_success=on_success,
        ))
        return self
    
    def get_step(self, name: str) -> Optional[WorkflowStep]:
        """이름으로 단계 검색"""
        for step in self.steps:
            if step.name == name:
                return step
        return None
    
    def get_entry_step(self) -> Optional[WorkflowStep]:
        """시작 단계 반환"""
        if self.steps:
            return self.steps[0]
        return None
    
    def build_graph(self, agents: dict, llm: Any, tool_registry: Any = None):
        """
        워크플로우를 LangGraph StateGraph로 변환
        
        Args:
            agents: AgentConfig 딕셔너리
            llm: LangChain LLM 인스턴스
            tool_registry: ToolRegistry 인스턴스
        
        Returns:
            CompiledStateGraph
        """
        try:
            from langgraph.graph import StateGraph, START, END
            from langgraph.checkpoint.memory import MemorySaver
        except ImportError:
            raise ImportError("langgraph 패키지가 필요합니다: pip install langgraph")
        
        from ..state import AgentState
        from ..agents.base import AgentFactory
        
        graph = StateGraph(AgentState)
        
        # 에이전트 컴파일
        compiled_agents = {}
        for step in self.steps:
            if step.agent not in compiled_agents and step.agent in agents:
                compiled_agents[step.agent] = AgentFactory.create(
                    agents[step.agent], llm, tool_registry
                )
        
        # 노드 생성
        for step in self.steps:
            node_func = self._create_step_node(step, compiled_agents)
            graph.add_node(step.name, node_func)
        
        # 엣지 생성
        if self.steps:
            graph.add_edge(START, self.steps[0].name)
        
        for step in self.steps:
            if step.next_step:
                graph.add_edge(step.name, step.next_step)
            else:
                # 마지막 단계
                graph.add_edge(step.name, END)
        
        return graph.compile(checkpointer=MemorySaver())
    
    def _create_step_node(
        self, 
        step: WorkflowStep, 
        compiled_agents: dict
    ) -> Callable:
        """단계 노드 함수 생성"""
        
        def node_func(state: dict) -> dict:
            agent = compiled_agents.get(step.agent)
            if not agent:
                return {
                    "errors": state.get("errors", []) + [f"에이전트를 찾을 수 없습니다: {step.agent}"],
                    "current_step": step.name,
                }
            
            try:
                # 작업 템플릿 처리
                context = state.get("context", {})
                task = step.get_task(context)
                
                # 에이전트 실행
                result = agent.invoke({
                    "messages": [{"role": "user", "content": task}]
                })
                
                # 결과에서 산출물 추출 (있다면)
                new_messages = result.get("messages", [])
                artifacts = state.get("artifacts", {}).copy()
                
                # 마지막 메시지를 산출물로 저장
                if new_messages:
                    last_msg = new_messages[-1]
                    content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
                    artifacts[f"{step.name}_result"] = content
                
                return {
                    "messages": state.get("messages", []) + new_messages,
                    "artifacts": artifacts,
                    "current_step": step.name,
                }
                
            except Exception as e:
                return {
                    "errors": state.get("errors", []) + [f"단계 실행 오류 ({step.name}): {e}"],
                    "current_step": step.name,
                }
        
        return node_func
    
    def to_dict(self) -> dict:
        """워크플로우를 딕셔너리로 변환"""
        return {
            "name": self.name,
            "description": self.description,
            "steps": [
                {
                    "name": s.name,
                    "agent": s.agent,
                    "task_template": s.task_template,
                    "next_step": s.next_step,
                }
                for s in self.steps
            ],
        }


class StaticWorkflowRunner:
    """
    정적 워크플로우 실행기
    """
    
    def __init__(
        self,
        workflow: BaseWorkflow,
        agents: dict,
        llm: Any,
        tool_registry: Any = None
    ):
        self.workflow = workflow
        self.agents = agents
        self.llm = llm
        self.tool_registry = tool_registry
        self._graph = None
    
    def build(self) -> "StaticWorkflowRunner":
        """그래프 빌드"""
        self._graph = self.workflow.build_graph(
            self.agents, self.llm, self.tool_registry
        )
        return self
    
    def run(
        self,
        task: str,
        context: dict = None,
        thread_id: str = "default"
    ) -> dict:
        """
        워크플로우 실행
        
        Args:
            task: 사용자 작업 요청
            context: 변환 컨텍스트
            thread_id: 체크포인트용 스레드 ID
        
        Returns:
            최종 상태
        """
        if not self._graph:
            self.build()
        
        from ..state import create_initial_state
        
        initial_state = create_initial_state(task, context, mode="static")
        config = {"configurable": {"thread_id": thread_id}}
        
        return self._graph.invoke(initial_state, config)
