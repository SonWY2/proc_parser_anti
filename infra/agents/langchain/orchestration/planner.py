"""
동적 계획 수립 (Planner)

현재 상태와 목표를 분석하여 다음 행동 계획을 동적으로 생성합니다.
"""
import json
from typing import Any, Optional


class Planner:
    """
    동적 계획 수립자
    
    사용자 요청과 현재 상태를 분석하여 다음 수행할 작업 계획을 생성합니다.
    Self-Evolve를 위해 과거 교훈을 참조합니다.
    """
    
    SYSTEM_PROMPT = """당신은 Pro*C to Java 변환 프로젝트의 **계획 수립 전문가**입니다.

## 사용 가능한 전문 에이전트
{agents_description}

## 현재 상태
- 완료된 단계: {executed_steps}
- 중간 산출물: {artifacts}
- 이전 반성: {reflections}
- 과거 교훈: {lessons}

## 작업
사용자 요청과 현재 상태를 분석하여 다음 수행할 작업 계획을 수립하세요.

## 응답 형식 (JSON)
```json
{{
    "analysis": "현재 상황 분석",
    "next_steps": ["다음 작업 1", "다음 작업 2", ...],
    "rationale": "이 계획을 선택한 이유"
}}
```

계획은 구체적이고 실행 가능해야 합니다.
작업이 완료되었다면 next_steps를 빈 배열로 반환하세요.
"""
    
    def __init__(
        self,
        llm: Any,
        agents: dict,
        memory: Optional[Any] = None
    ):
        """
        Args:
            llm: LangChain LLM 인스턴스
            agents: 사용 가능한 에이전트 설정 딕셔너리
            memory: EpisodicMemory 인스턴스 (선택)
        """
        self.llm = llm
        self.agents = agents
        self.memory = memory
    
    def _format_agents_description(self) -> str:
        """에이전트 설명 포맷팅"""
        lines = []
        for name, config in self.agents.items():
            lines.append(f"- **{name}**: {config.description}")
        return "\n".join(lines)
    
    def _get_lessons(self, task: str) -> list[str]:
        """관련 교훈 검색"""
        if self.memory:
            return self.memory.get_relevant_lessons(task, k=3)
        return []
    
    def plan(self, state: dict) -> dict:
        """
        현재 상태 기반 동적 계획 생성
        
        Args:
            state: DynamicAgentState
        
        Returns:
            상태 업데이트 딕셔너리
        """
        # 메시지에서 원본 작업 추출
        messages = state.get("messages", [])
        task = ""
        if messages:
            last_msg = messages[-1]
            if isinstance(last_msg, dict):
                task = last_msg.get("content", "")
            elif hasattr(last_msg, "content"):
                task = last_msg.content
        
        # 프롬프트 구성
        prompt = self.SYSTEM_PROMPT.format(
            agents_description=self._format_agents_description(),
            executed_steps=state.get("executed_steps", []),
            artifacts=list(state.get("artifacts", {}).keys()),
            reflections=state.get("reflections", [])[-3:],  # 최근 3개만
            lessons=self._get_lessons(task),
        )
        
        # LLM 호출
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            
            response = self.llm.invoke([
                SystemMessage(content=prompt),
                HumanMessage(content=f"사용자 요청: {task}")
            ])
            
            # 응답 파싱
            content = response.content
            
            # JSON 추출
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]
            else:
                json_str = content
            
            result = json.loads(json_str.strip())
            next_steps = result.get("next_steps", [])
            
        except Exception as e:
            # 파싱 실패 시 기본 계획
            next_steps = self._generate_default_plan(state)
        
        return {
            "current_plan": next_steps,
        }
    
    def _generate_default_plan(self, state: dict) -> list[str]:
        """기본 계획 생성 (LLM 실패 시 폴백)"""
        executed = set(state.get("executed_steps", []))
        
        # 기본 순서
        default_order = [
            "종속성 분석",
            "코드 파싱",
            "SQL 분석",
            "컨텍스트 생성",
            "Java 변환",
            "품질 검증",
        ]
        
        remaining = [step for step in default_order if step not in executed]
        return remaining[:2]  # 다음 2단계만
