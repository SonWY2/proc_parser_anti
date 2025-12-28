"""
오케스트레이터

메인 에이전트가 서브에이전트를 조율하고 관리합니다.
"""

import concurrent.futures
from pathlib import Path
from typing import Optional, List, Dict, Any

from .agent_loader import AgentLoader, AgentDefinition
from .tools import ToolRegistry
from .subagent import Subagent
from .result import SubagentResult
from .llm_client import LLMClient, LLMConfig


class Orchestrator:
    """서브에이전트 오케스트레이터"""
    
    DEFAULT_AGENT_DIRS = [
        '.agents',           # 프로젝트 수준
        '.claude/agents',    # Claude Code 호환
    ]
    
    def __init__(
        self, 
        agent_dirs: Optional[List[Path]] = None,
        llm_config: Optional[LLMConfig] = None,
        max_parallel: int = 5
    ):
        """
        Args:
            agent_dirs: 에이전트 정의 파일 디렉토리 목록
            llm_config: LLM 설정
            max_parallel: 최대 병렬 실행 수
        """
        self.agent_dirs = agent_dirs or []
        self.llm_config = llm_config
        self.max_parallel = max_parallel
        
        self.loader = AgentLoader()
        self.registry = ToolRegistry()
        self._agents: Dict[str, AgentDefinition] = {}
        self._subagents: Dict[str, Subagent] = {}
    
    def add_agent_directory(self, directory: Path) -> None:
        """에이전트 디렉토리 추가"""
        if directory not in self.agent_dirs:
            self.agent_dirs.append(directory)
            self.loader.add_directory(directory)
    
    def load_agents(self, base_path: Optional[Path] = None) -> Dict[str, AgentDefinition]:
        """
        모든 에이전트 로드
        
        Args:
            base_path: 기준 경로 (None이면 현재 디렉토리)
            
        Returns:
            로드된 에이전트 딕셔너리
        """
        base = base_path or Path.cwd()
        
        # 기본 디렉토리 검색
        for default_dir in self.DEFAULT_AGENT_DIRS:
            path = base / default_dir
            if path.exists():
                self.loader.add_directory(path)
        
        # 사용자 지정 디렉토리 추가
        for agent_dir in self.agent_dirs:
            self.loader.add_directory(agent_dir)
        
        # 에이전트 로드
        self._agents = self.loader.load_all()
        
        # 서브에이전트 인스턴스 생성
        self._create_subagents()
        
        return self._agents
    
    def _create_subagents(self) -> None:
        """서브에이전트 인스턴스 생성"""
        llm_client = LLMClient(self.llm_config)
        
        self._subagents = {
            name: Subagent(definition, llm_client, self.registry)
            for name, definition in self._agents.items()
        }
    
    def get_agent(self, name: str) -> Optional[AgentDefinition]:
        """이름으로 에이전트 정의 조회"""
        return self._agents.get(name)
    
    def list_agents(self) -> List[Dict[str, str]]:
        """로드된 에이전트 목록"""
        return [
            {
                'name': agent.name,
                'description': agent.description,
                'tools': agent.tools,
                'model': agent.model
            }
            for agent in self._agents.values()
        ]
    
    def delegate(self, agent_name: str, task: str) -> SubagentResult:
        """
        서브에이전트에게 작업 위임
        
        Args:
            agent_name: 에이전트 이름
            task: 수행할 작업
            
        Returns:
            SubagentResult: 실행 결과
        """
        subagent = self._subagents.get(agent_name)
        if not subagent:
            return SubagentResult(
                success=False,
                output="",
                agent_name=agent_name,
                execution_time=0,
                error=f"에이전트를 찾을 수 없습니다: {agent_name}"
            )
        
        return subagent.run(task)
    
    def auto_delegate(self, user_request: str) -> Optional[SubagentResult]:
        """
        사용자 요청에 맞는 에이전트 자동 선택 및 실행
        
        우선순위:
        1. 오케스트레이터 정의의 delegate_rules
        2. 에이전트의 description 매칭
        
        Args:
            user_request: 사용자 요청
            
        Returns:
            SubagentResult 또는 None (매칭되는 에이전트 없음)
        """
        # 1. 오케스트레이터 규칙으로 먼저 찾기
        agent_name = self.loader.find_agent_by_orchestrator(user_request)
        if agent_name and agent_name in self._subagents:
            print(f"[오케스트레이터] 규칙 매칭: {agent_name}")
            return self.delegate(agent_name, user_request)
        
        # 2. 에이전트 description 매칭
        matching_agents = self.loader.find_matching_agents(user_request)
        
        if not matching_agents:
            # 3. 기본 에이전트 사용
            if self.loader.orchestrator and self.loader.orchestrator.default_agent:
                default_agent = self.loader.orchestrator.default_agent
                if default_agent in self._subagents:
                    print(f"[오케스트레이터] 기본 에이전트 사용: {default_agent}")
                    return self.delegate(default_agent, user_request)
            return None
        
        # 첫 번째 매칭 에이전트 사용
        agent = matching_agents[0]
        return self.delegate(agent.name, user_request)

    
    def delegate_parallel(
        self, 
        tasks: List[Dict[str, str]]
    ) -> List[SubagentResult]:
        """
        여러 작업 병렬 실행
        
        Args:
            tasks: [{"agent": "에이전트이름", "task": "작업내용"}, ...]
            
        Returns:
            SubagentResult 목록
        """
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_parallel) as executor:
            futures = {
                executor.submit(self.delegate, t['agent'], t['task']): t
                for t in tasks
            }
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    task = futures[future]
                    results.append(SubagentResult(
                        success=False,
                        output="",
                        agent_name=task['agent'],
                        execution_time=0,
                        error=str(e)
                    ))
        
        return results
    
    def chain(self, steps: List[Dict[str, str]], 
              pass_context: bool = True) -> List[SubagentResult]:
        """
        에이전트 체인 실행 - 이전 에이전트의 출력을 다음 입력으로 전달
        
        Args:
            steps: [{"agent": "에이전트이름", "task": "작업내용"}, ...]
            pass_context: 이전 출력을 다음 태스크에 전달할지 여부
            
        Returns:
            각 단계의 SubagentResult 목록
        """
        results = []
        previous_output = ""
        
        for i, step in enumerate(steps):
            agent_name = step.get('agent', '')
            task = step.get('task', '')
            
            # 이전 출력을 태스크에 추가
            if pass_context and previous_output:
                task = f"{task}\n\n[이전 단계 결과]\n{previous_output}"
            
            # 에이전트 실행
            result = self.delegate(agent_name, task)
            results.append(result)
            
            # 이전 출력 업데이트
            if result.success:
                previous_output = result.output
            else:
                # 실패 시 체인 중단 옵션
                print(f"[체인] 단계 {i+1} 실패: {agent_name}")
                break
        
        return results
    
    def pipe(self, task: str, *agent_names: str) -> SubagentResult:
        """
        간단한 파이프라인 - 여러 에이전트를 순차 연결
        
        Args:
            task: 초기 작업
            *agent_names: 순차 실행할 에이전트 이름들
            
        Returns:
            마지막 에이전트의 결과
        """
        if not agent_names:
            return SubagentResult(
                success=False,
                output="",
                agent_name="pipe",
                execution_time=0,
                error="에이전트가 지정되지 않았습니다"
            )
        
        steps = [{"agent": agent_names[0], "task": task}]
        for agent_name in agent_names[1:]:
            steps.append({"agent": agent_name, "task": "이전 결과를 분석하고 처리하세요."})
        
        results = self.chain(steps)
        return results[-1] if results else SubagentResult(
            success=False,
            output="",
            agent_name="pipe",
            execution_time=0,
            error="체인 실행 결과 없음"
        )
    
    def reload_agents(self, base_path: Optional[Path] = None) -> Dict[str, AgentDefinition]:
        """에이전트 재로드"""
        self._agents.clear()
        self._subagents.clear()
        return self.load_agents(base_path)
    
    @property
    def agents(self) -> Dict[str, AgentDefinition]:
        """로드된 에이전트"""
        return self._agents
    
    @property
    def available_tools(self) -> List[str]:
        """사용 가능한 도구 목록"""
        return self.registry.available_tools
