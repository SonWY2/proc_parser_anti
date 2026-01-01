"""
동적 라우터 (Router)

계획에 따라 적절한 전문 에이전트를 동적으로 선택합니다.
"""
import json
from typing import Any, Optional


class Router:
    """
    동적 에이전트 라우터
    
    현재 계획의 다음 작업에 가장 적합한 에이전트를 선택합니다.
    """
    
    ROUTING_PROMPT = """다음 작업에 가장 적합한 에이전트를 선택하세요.

## 작업
{task}

## 사용 가능한 에이전트
{agents_description}

## 응답 형식 (JSON)
```json
{{
    "selected_agent": "에이전트 이름",
    "reason": "선택 이유"
}}
```

정확히 하나의 에이전트만 선택하세요.
"""
    
    # 키워드 기반 빠른 매핑 (LLM 호출 없이 사용)
    KEYWORD_MAPPING = {
        "dependency_analyst": ["종속성", "dependency", "include", "#include", "헤더", "header"],
        "parsing_agent": ["파싱", "parse", "함수", "변수", "구조체", "function", "struct"],
        "sql_analyst": ["sql", "exec sql", "쿼리", "query", "mybatis", "커서", "cursor"],
        "context_engineer": ["컨텍스트", "context", "요약", "통합", "정리"],
        "transformer": ["변환", "convert", "java", "transform", "생성"],
        "build_debug": ["빌드", "build", "컴파일", "compile", "디버그", "debug", "오류"],
        "critic": ["평가", "검증", "review", "품질", "quality", "검사"],
    }
    
    def __init__(
        self,
        llm: Any,
        agents: dict,
        use_llm_routing: bool = True
    ):
        """
        Args:
            llm: LangChain LLM 인스턴스
            agents: 사용 가능한 에이전트 설정 딕셔너리
            use_llm_routing: LLM 기반 라우팅 사용 여부 (False면 키워드 기반)
        """
        self.llm = llm
        self.agents = agents
        self.use_llm_routing = use_llm_routing
    
    def _format_agents_description(self) -> str:
        """에이전트 설명 포맷팅"""
        lines = []
        for name, config in self.agents.items():
            lines.append(f"- **{name}**: {config.description}")
        return "\n".join(lines)
    
    def _keyword_route(self, task: str) -> Optional[str]:
        """키워드 기반 빠른 라우팅"""
        task_lower = task.lower()
        
        for agent_name, keywords in self.KEYWORD_MAPPING.items():
            if agent_name not in self.agents:
                continue
            for keyword in keywords:
                if keyword.lower() in task_lower:
                    return agent_name
        
        return None
    
    def route(self, state: dict) -> dict:
        """
        계획에 따라 적절한 에이전트 선택
        
        Args:
            state: DynamicAgentState
        
        Returns:
            상태 업데이트 딕셔너리
        """
        current_plan = state.get("current_plan", [])
        
        if not current_plan:
            return {"selected_agent": "", "is_complete": True}
        
        task = current_plan[0]
        
        # 1. 먼저 키워드 기반 빠른 라우팅 시도
        selected = self._keyword_route(task)
        
        # 2. 키워드 매칭 실패하고 LLM 라우팅이 활성화된 경우
        if not selected and self.use_llm_routing:
            selected = self._llm_route(task)
        
        # 3. 여전히 실패하면 기본 에이전트
        if not selected:
            selected = self._get_default_agent()
        
        return {
            "selected_agent": selected,
            "iteration_count": state.get("iteration_count", 0) + 1,
        }
    
    def _llm_route(self, task: str) -> Optional[str]:
        """LLM 기반 라우팅"""
        prompt = self.ROUTING_PROMPT.format(
            task=task,
            agents_description=self._format_agents_description(),
        )
        
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            
            response = self.llm.invoke([
                SystemMessage(content=prompt),
                HumanMessage(content="에이전트를 선택하세요.")
            ])
            
            content = response.content
            
            # JSON 추출
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]
            else:
                json_str = content
            
            result = json.loads(json_str.strip())
            selected = result.get("selected_agent", "")
            
            # 유효성 검증
            if selected in self.agents:
                return selected
            
        except Exception:
            pass
        
        return None
    
    def _get_default_agent(self) -> str:
        """기본 에이전트 반환"""
        # 우선순위: dependency_analyst > parsing_agent > transformer
        for name in ["dependency_analyst", "parsing_agent", "transformer"]:
            if name in self.agents:
                return name
        
        # 아무거나 첫 번째
        if self.agents:
            return next(iter(self.agents.keys()))
        
        return ""
