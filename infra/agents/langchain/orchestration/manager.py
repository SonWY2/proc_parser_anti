"""
동적 매니저 (DynamicManager)

Reflection + Self-Evolve 기반 동적 오케스트레이터
"""
from typing import Any, Optional


class DynamicManager:
    """
    Reflection + Self-Evolve 기반 동적 오케스트레이터
    
    작동 방식:
    1. Planner가 사용자 요청을 분석하여 초기 계획 생성
    2. Router가 계획의 각 단계에 적합한 에이전트 선택
    3. 선택된 에이전트가 작업 수행
    4. Reflector가 결과 분석 및 자기 비평
    5. 필요시 계획 수정 후 반복 (Self-Evolve)
    6. 완료 조건 충족 시 종료
    """
    
    def __init__(
        self,
        agents: dict,
        llm: Any,
        tool_registry: Any = None,
        memory: Optional[Any] = None,
        max_iterations: int = 10
    ):
        """
        Args:
            agents: AgentConfig 딕셔너리
            llm: LangChain LLM 인스턴스
            tool_registry: ToolRegistry 인스턴스
            memory: EpisodicMemory 인스턴스
            max_iterations: 최대 반복 횟수
        """
        self.agents = agents
        self.llm = llm
        self.tool_registry = tool_registry
        self.max_iterations = max_iterations
        
        # 메모리 초기화
        if memory is None:
            from ..memory import EpisodicMemory
            memory = EpisodicMemory()
        self.memory = memory
        
        # 컴포넌트 초기화
        from .planner import Planner
        from .router import Router
        from .reflector import Reflector
        
        self.planner = Planner(llm, agents, memory)
        self.router = Router(llm, agents)
        self.reflector = Reflector(llm, memory)
        
        # 컴파일된 에이전트 캐시
        self._compiled_agents = {}
    
    def _get_compiled_agent(self, agent_name: str):
        """컴파일된 에이전트 가져오기 (캐싱)"""
        if agent_name not in self._compiled_agents:
            from ..agents.base import AgentFactory
            config = self.agents.get(agent_name)
            if config:
                self._compiled_agents[agent_name] = AgentFactory.create(
                    config, self.llm, self.tool_registry
                )
        return self._compiled_agents.get(agent_name)
    
    def _execute_agent(self, state: dict) -> dict:
        """선택된 에이전트 실행"""
        agent_name = state.get("selected_agent", "")
        if not agent_name:
            return {"errors": state.get("errors", []) + ["에이전트가 선택되지 않았습니다."]}
        
        agent = self._get_compiled_agent(agent_name)
        if not agent:
            return {"errors": state.get("errors", []) + [f"에이전트를 찾을 수 없습니다: {agent_name}"]}
        
        try:
            # 현재 작업 가져오기
            current_plan = state.get("current_plan", [])
            task = current_plan[0] if current_plan else ""
            
            # 에이전트 실행
            result = agent.invoke({
                "messages": [{"role": "user", "content": task}]
            })
            
            # 메시지 업데이트
            new_messages = result.get("messages", [])
            
            return {
                "messages": state.get("messages", []) + new_messages,
            }
            
        except Exception as e:
            return {
                "errors": state.get("errors", []) + [f"에이전트 실행 오류: {e}"],
            }
    
    def _self_evolve(self, state: dict) -> dict:
        """
        Self-Evolve: 반성 결과를 바탕으로 계획 조정
        """
        pending = state.get("pending_improvements", [])
        
        if pending:
            # 개선 필요 항목이 있으면 계획에 추가
            current_plan = state.get("current_plan", [])
            # 개선 작업을 계획 앞에 추가
            updated_plan = pending + current_plan
            return {
                "current_plan": updated_plan,
                "pending_improvements": [],  # 처리됨
            }
        
        return {}
    
    def build_graph(self):
        """동적 오케스트레이션 그래프 구성"""
        try:
            from langgraph.graph import StateGraph, START, END
            from langgraph.checkpoint.memory import MemorySaver
        except ImportError:
            raise ImportError("langgraph 패키지가 필요합니다: pip install langgraph")
        
        from ..state import DynamicAgentState
        
        graph = StateGraph(DynamicAgentState)
        
        # 노드 추가
        graph.add_node("plan", self.planner.plan)
        graph.add_node("route", self.router.route)
        graph.add_node("execute", self._execute_agent)
        graph.add_node("reflect", self.reflector.reflect)
        graph.add_node("evolve", self._self_evolve)
        
        # 엣지 구성
        graph.add_edge(START, "plan")
        graph.add_edge("plan", "route")
        graph.add_edge("route", "execute")
        graph.add_edge("execute", "reflect")
        
        # 조건부 엣지: 계속 또는 종료
        graph.add_conditional_edges(
            "reflect",
            self.reflector.should_continue,
            {
                "continue": "evolve",
                "complete": END,
            }
        )
        graph.add_edge("evolve", "plan")  # 반복
        
        return graph.compile(checkpointer=MemorySaver())
    
    def run(
        self,
        task: str,
        context: dict = None,
        thread_id: str = "default"
    ) -> dict:
        """
        동적 오케스트레이션 실행
        
        Args:
            task: 사용자 작업 요청
            context: 변환 컨텍스트 (target_dir 등)
            thread_id: 체크포인트용 스레드 ID
        
        Returns:
            최종 상태
        """
        from ..state import create_initial_state
        
        # 그래프 빌드
        graph = self.build_graph()
        
        # 초기 상태
        initial_state = create_initial_state(task, context, mode="dynamic")
        
        # 실행
        config = {"configurable": {"thread_id": thread_id}}
        final_state = graph.invoke(initial_state, config)
        
        return final_state
    
    async def arun(
        self,
        task: str,
        context: dict = None,
        thread_id: str = "default"
    ) -> dict:
        """비동기 실행"""
        from ..state import create_initial_state
        
        graph = self.build_graph()
        initial_state = create_initial_state(task, context, mode="dynamic")
        config = {"configurable": {"thread_id": thread_id}}
        
        final_state = await graph.ainvoke(initial_state, config)
        return final_state
