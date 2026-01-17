"""
서브에이전트 실행 엔진

독립 컨텍스트에서 작업을 실행하고 결과만 반환합니다.
"""

import time
from typing import Optional, List, Dict, Any
from datetime import datetime

from .agent_loader import AgentDefinition
from .tools import ToolRegistry, ToolResult
from .result import SubagentResult, ToolCallRecord
from .llm_client import LLMClient


class Subagent:
    """서브에이전트 실행 엔진"""
    
    MAX_ITERATIONS = 10  # 최대 반복 횟수 (무한 루프 방지)
    
    def __init__(
        self, 
        definition: AgentDefinition, 
        llm_client: LLMClient,
        tool_registry: Optional[ToolRegistry] = None
    ):
        """
        Args:
            definition: 에이전트 정의
            llm_client: LLM 클라이언트
            tool_registry: 도구 레지스트리 (None이면 기본값 사용)
        """
        self.definition = definition
        self.llm = llm_client
        self.registry = tool_registry or ToolRegistry()
        
        # 허용된 도구만 가져오기
        self.tools = self.registry.get_allowed_tools(definition.tools)
        
        # 독립 컨텍스트 (대화 기록)
        self.context: List[Dict[str, str]] = []
        self.tool_call_records: List[ToolCallRecord] = []
    
    def _build_system_message(self) -> Dict[str, str]:
        """시스템 메시지 생성"""
        tool_list = ", ".join(self.tools.keys()) if self.tools else "없음"
        
        system_content = f"""{self.definition.system_prompt}

사용 가능한 도구: {tool_list}

응답 규칙:
1. 도구를 사용할 때는 function call을 사용하세요.
2. 작업 완료 시 최종 결과를 텍스트로 반환하세요.
3. 도구 실행 결과를 바탕으로 다음 행동을 결정하세요.
"""
        return {"role": "system", "content": system_content}
    
    def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """도구 실행"""
        tool = self.tools.get(tool_name)
        if not tool:
            return ToolResult(False, "", f"허용되지 않은 도구: {tool_name}")
        
        return tool.execute(**arguments)
    
    def run(self, task: str) -> SubagentResult:
        """
        작업 실행
        
        Args:
            task: 수행할 작업 설명
            
        Returns:
            SubagentResult: 실행 결과
        """
        start_time = time.time()
        
        # 컨텍스트 초기화
        self.context = [self._build_system_message()]
        self.tool_call_records = []
        
        # 사용자 태스크 추가
        self.context.append({"role": "user", "content": task})
        
        # 도구 스키마 준비
        tool_schemas = [self.tools[name].get_schema() for name in self.tools]
        
        final_output = ""
        iteration = 0
        
        while iteration < self.MAX_ITERATIONS:
            iteration += 1
            
            # LLM 호출
            response = self.llm.chat(
                messages=self.context,
                tools=tool_schemas if tool_schemas else None,
                temperature=0.7,
                max_tokens=4096
            )
            
            if not response['success']:
                return SubagentResult(
                    success=False,
                    output="",
                    agent_name=self.definition.name,
                    execution_time=time.time() - start_time,
                    tool_calls=self.tool_call_records,
                    error=response['error']
                )
            
            # 도구 호출이 있는 경우
            if response['tool_calls']:
                for tool_call in response['tool_calls']:
                    tool_name = tool_call['name']
                    arguments = tool_call['arguments']
                    
                    # 도구 실행
                    result = self._execute_tool(tool_name, arguments)
                    
                    # 기록 저장
                    record = ToolCallRecord(
                        tool_name=tool_name,
                        arguments=arguments,
                        result=result.output if result.success else "",
                        success=result.success,
                        error=result.error
                    )
                    self.tool_call_records.append(record)
                    
                    # 컨텍스트에 도구 결과 추가
                    self.context.append({
                        "role": "assistant",
                        "content": f"[도구 호출: {tool_name}]"
                    })
                    self.context.append({
                        "role": "user",
                        "content": f"[도구 결과]\n{result.output if result.success else result.error}"
                    })
            else:
                # 도구 호출 없이 텍스트 응답만 있는 경우 -> 완료
                final_output = response['content']
                break
        
        # 최대 반복 초과 시
        if iteration >= self.MAX_ITERATIONS and not final_output:
            final_output = "최대 반복 횟수에 도달했습니다. 마지막 상태를 반환합니다."
        
        return SubagentResult(
            success=True,
            output=final_output,
            agent_name=self.definition.name,
            execution_time=time.time() - start_time,
            tool_calls=self.tool_call_records,
            context_length=len(str(self.context))
        )
    
    def reset(self) -> None:
        """컨텍스트 초기화"""
        self.context = []
        self.tool_call_records = []
    
    def save_context(self, file_path: str) -> bool:
        """
        대화 컨텍스트를 파일로 저장
        
        Args:
            file_path: 저장할 파일 경로
            
        Returns:
            저장 성공 여부
        """
        import json
        from pathlib import Path
        from dataclasses import asdict
        
        try:
            data = {
                "agent_name": self.definition.name,
                "context": self.context,
                "tool_calls": [asdict(tc) for tc in self.tool_call_records],
                "saved_at": datetime.now().isoformat()
            }
            
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            return True
        except Exception as e:
            print(f"컨텍스트 저장 실패: {e}")
            return False
    
    def load_context(self, file_path: str) -> bool:
        """
        저장된 컨텍스트 로드
        
        Args:
            file_path: 로드할 파일 경로
            
        Returns:
            로드 성공 여부
        """
        import json
        from pathlib import Path
        
        try:
            path = Path(file_path)
            if not path.exists():
                print(f"파일이 존재하지 않습니다: {file_path}")
                return False
            
            data = json.loads(path.read_text(encoding='utf-8'))
            
            # 에이전트 이름 확인
            if data.get("agent_name") != self.definition.name:
                print(f"에이전트 불일치: 저장={data.get('agent_name')}, 현재={self.definition.name}")
                return False
            
            # 컨텍스트 복원
            self.context = data.get("context", [])
            
            # 도구 호출 기록 복원
            self.tool_call_records = [
                ToolCallRecord(
                    tool_name=tc["tool_name"],
                    arguments=tc["arguments"],
                    result=tc.get("result", ""),
                    success=tc.get("success", True),
                    error=tc.get("error")
                )
                for tc in data.get("tool_calls", [])
            ]
            
            return True
        except Exception as e:
            print(f"컨텍스트 로드 실패: {e}")
            return False
    
    def continue_run(self, task: str) -> SubagentResult:
        """
        기존 컨텍스트를 유지하면서 추가 작업 실행
        
        Args:
            task: 추가 작업 설명
            
        Returns:
            SubagentResult: 실행 결과
        """
        # 컨텍스트가 비어있으면 일반 run 호출
        if not self.context:
            return self.run(task)
        
        start_time = time.time()
        
        # 추가 태스크를 컨텍스트에 추가
        self.context.append({"role": "user", "content": task})
        
        # 도구 스키마 준비
        tool_schemas = [self.tools[name].get_schema() for name in self.tools]
        
        final_output = ""
        iteration = 0
        
        while iteration < self.MAX_ITERATIONS:
            iteration += 1
            
            # LLM 호출
            response = self.llm.chat(
                messages=self.context,
                tools=tool_schemas if tool_schemas else None,
                temperature=0.7,
                max_tokens=4096
            )
            
            if not response['success']:
                return SubagentResult(
                    success=False,
                    output="",
                    agent_name=self.definition.name,
                    execution_time=time.time() - start_time,
                    tool_calls=self.tool_call_records,
                    error=response['error']
                )
            
            # 도구 호출이 있는 경우
            if response['tool_calls']:
                for tool_call in response['tool_calls']:
                    tool_name = tool_call['name']
                    arguments = tool_call['arguments']
                    
                    # 도구 실행
                    result = self._execute_tool(tool_name, arguments)
                    
                    # 기록 저장
                    record = ToolCallRecord(
                        tool_name=tool_name,
                        arguments=arguments,
                        result=result.output if result.success else "",
                        success=result.success,
                        error=result.error
                    )
                    self.tool_call_records.append(record)
                    
                    # 컨텍스트에 도구 결과 추가
                    self.context.append({
                        "role": "assistant",
                        "content": f"[도구 호출: {tool_name}]"
                    })
                    self.context.append({
                        "role": "user",
                        "content": f"[도구 결과]\n{result.output if result.success else result.error}"
                    })
            else:
                # 도구 호출 없이 텍스트 응답만 있는 경우 -> 완료
                final_output = response['content']
                break
        
        if iteration >= self.MAX_ITERATIONS and not final_output:
            final_output = "최대 반복 횟수에 도달했습니다."
        
        return SubagentResult(
            success=True,
            output=final_output,
            agent_name=self.definition.name,
            execution_time=time.time() - start_time,
            tool_calls=self.tool_call_records,
            context_length=len(str(self.context))
        )
