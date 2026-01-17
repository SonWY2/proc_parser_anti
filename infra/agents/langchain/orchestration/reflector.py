"""
자기 반성 (Reflector)

실행 결과를 분석하고 자기 비평을 수행합니다.
Self-Evolve를 위해 교훈을 추출하여 메모리에 저장합니다.
"""
import json
from typing import Any, Optional


class Reflector:
    """
    자기 반성 및 자기 비평
    
    에이전트 실행 결과를 분석하고 품질을 평가합니다.
    Self-Evolve를 위해 교훈을 추출하여 메모리에 저장합니다.
    """
    
    REFLECTION_PROMPT = """방금 수행한 작업을 분석하세요.

## 실행 정보
- 실행한 에이전트: {agent_name}
- 작업 내용: {task}
- 결과 요약: {result_summary}

## 이전 계획
{current_plan}

## 평가 기준
1. 작업이 성공적으로 완료되었는가?
2. 결과물의 품질은 어떠한가? (1-10)
3. 개선이 필요한 점은 무엇인가?
4. 다음 단계로 진행해도 되는가?
5. 이 경험에서 배울 수 있는 교훈은?

## 응답 형식 (JSON)
```json
{{
    "success": true/false,
    "quality_score": 1-10,
    "analysis": "결과 분석",
    "improvements": ["개선점 1", "개선점 2"],
    "proceed": true/false,
    "lesson": "이 작업에서 배운 교훈 (향후 유사 작업에 적용)"
}}
```
"""
    
    def __init__(
        self,
        llm: Any,
        memory: Optional[Any] = None
    ):
        """
        Args:
            llm: LangChain LLM 인스턴스
            memory: EpisodicMemory 인스턴스 (선택)
        """
        self.llm = llm
        self.memory = memory
    
    def reflect(self, state: dict) -> dict:
        """
        결과 분석 및 자기 비평
        
        Args:
            state: DynamicAgentState
        
        Returns:
            상태 업데이트 딕셔너리
        """
        # 최근 실행 정보 추출
        agent_name = state.get("selected_agent", "unknown")
        current_plan = state.get("current_plan", [])
        task = current_plan[0] if current_plan else "unknown"
        
        # 결과 요약 (마지막 메시지에서)
        messages = state.get("messages", [])
        result_summary = ""
        if messages:
            last_msg = messages[-1]
            if isinstance(last_msg, dict):
                result_summary = last_msg.get("content", "")[:500]
            elif hasattr(last_msg, "content"):
                result_summary = last_msg.content[:500]
        
        # 프롬프트 구성
        prompt = self.REFLECTION_PROMPT.format(
            agent_name=agent_name,
            task=task,
            result_summary=result_summary,
            current_plan=current_plan,
        )
        
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            
            response = self.llm.invoke([
                SystemMessage(content=prompt),
                HumanMessage(content="위 작업을 평가하고 JSON으로 응답하세요.")
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
            
        except Exception as e:
            # 파싱 실패 시 기본값
            result = {
                "success": True,
                "quality_score": 5,
                "analysis": f"자동 평가 실패: {e}",
                "improvements": [],
                "proceed": True,
                "lesson": "",
            }
        
        # 메모리에 교훈 저장 (Self-Evolve)
        lesson = result.get("lesson", "")
        if lesson and self.memory:
            self.memory.update_lesson(task, lesson)
            
            # 에피소드 저장
            self.memory.add_episode(
                task=task,
                agent=agent_name,
                actions=[task],
                outcome="success" if result.get("success") else "failure",
                quality_score=result.get("quality_score", 5),
                reflection=result.get("analysis", ""),
                lesson=lesson,
            )
        
        # 실행된 단계 업데이트
        executed_steps = state.get("executed_steps", []).copy()
        if task and task not in executed_steps:
            executed_steps.append(task)
        
        # 계획에서 완료된 단계 제거
        remaining_plan = current_plan[1:] if current_plan else []
        
        # 품질 점수 히스토리
        quality_scores = state.get("quality_scores", []).copy()
        quality_scores.append(result.get("quality_score", 5))
        
        # 완료 여부 판단
        is_complete = (
            result.get("proceed", True) and 
            len(remaining_plan) == 0 and
            result.get("success", True)
        )
        
        return {
            "reflections": state.get("reflections", []) + [result.get("analysis", "")],
            "quality_scores": quality_scores,
            "pending_improvements": result.get("improvements", []),
            "lessons_applied": state.get("lessons_applied", []) + ([lesson] if lesson else []),
            "executed_steps": executed_steps,
            "current_plan": remaining_plan,
            "is_complete": is_complete,
        }
    
    def should_continue(self, state: dict) -> str:
        """
        계속 진행 여부 판단 (조건부 엣지용)
        
        Returns:
            "continue" 또는 "complete"
        """
        if state.get("is_complete", False):
            return "complete"
        
        # 최대 반복 확인
        iteration = state.get("iteration_count", 0)
        if iteration >= 10:
            return "complete"
        
        # 품질이 너무 낮으면 개선 필요
        scores = state.get("quality_scores", [])
        if scores and scores[-1] < 3:
            return "continue"  # 개선 필요
        
        # 계획이 남아있으면 계속
        if state.get("current_plan"):
            return "continue"
        
        return "complete"
