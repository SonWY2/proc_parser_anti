"""
에이전트 정의 로더

.md 파일에서 YAML frontmatter와 시스템 프롬프트를 파싱합니다.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional
import yaml


@dataclass
class AgentDefinition:
    """에이전트 정의"""
    name: str
    description: str
    system_prompt: str
    file_path: Path
    tools: List[str] = field(default_factory=list)
    model: str = "inherit"  # 'sonnet', 'opus', 'haiku', 'inherit'
    self_improve: bool = False  # 자가개선 체크리스트 활성화
    
    def matches_request(self, user_request: str) -> bool:
        """사용자 요청이 이 에이전트의 description과 매칭되는지 확인"""
        # description에서 키워드 추출
        keywords = self.description.lower().split()
        request_lower = user_request.lower()
        
        # 주요 트리거 키워드 확인
        trigger_keywords = ['proactively', 'must be used', 'always use']
        has_trigger = any(kw in self.description.lower() for kw in trigger_keywords)
        
        if has_trigger:
            # 트리거 키워드가 있으면 더 관대하게 매칭
            match_count = sum(1 for kw in keywords if kw in request_lower)
            return match_count >= 2
        
        return False


@dataclass
class DelegateRule:
    """위임 규칙"""
    pattern: str  # 매칭 패턴 (정규식 또는 키워드)
    agent: str    # 위임할 에이전트 이름
    priority: int = 0  # 우선순위 (높을수록 먼저 매칭)
    
    def matches(self, text: str) -> bool:
        """텍스트가 패턴과 매칭되는지 확인"""
        import re
        try:
            # 정규식으로 시도
            if re.search(self.pattern, text, re.IGNORECASE):
                return True
        except re.error:
            # 정규식 실패 시 단순 키워드 매칭
            pass
        
        # 키워드 매칭
        return self.pattern.lower() in text.lower()


@dataclass
class OrchestratorDefinition:
    """오케스트레이터 정의"""
    name: str
    description: str
    system_prompt: str
    file_path: Path
    delegate_rules: List[DelegateRule] = field(default_factory=list)
    default_agent: Optional[str] = None  # 매칭되는 규칙 없을 때 기본 에이전트
    model: str = "inherit"
    
    def find_agent_for_request(self, user_request: str) -> Optional[str]:
        """요청에 맞는 에이전트 찾기"""
        # 우선순위 순으로 정렬
        sorted_rules = sorted(self.delegate_rules, key=lambda r: -r.priority)
        
        for rule in sorted_rules:
            if rule.matches(user_request):
                return rule.agent
        
        return self.default_agent





class AgentLoader:
    """에이전트 정의 파일 로더"""
    
    FRONTMATTER_PATTERN = re.compile(
        r'^---\s*\n(.*?)\n---\s*\n(.*)$',
        re.DOTALL
    )
    
    # v3: 공용 규칙 파일 (우선순위 순)
    GLOBAL_RULES_FILES = [
        "CLAUDE.md",          # Claude Code 호환
        "GLOBAL.md",          # 프로젝트 전역 규칙
        ".agents/GLOBAL.md",  # 에이전트 전용 규칙
    ]
    
    def __init__(self, agent_dirs: Optional[List[Path]] = None):
        """
        Args:
            agent_dirs: 에이전트 정의 파일을 검색할 디렉토리 목록
        """
        self.agent_dirs = agent_dirs or []
        self._agents: Dict[str, AgentDefinition] = {}
        self._orchestrator: Optional[OrchestratorDefinition] = None
        self._global_rules: str = ""  # v3: 공용 규칙 캐시
    
    def add_directory(self, directory: Path) -> None:
        """에이전트 검색 디렉토리 추가"""
        if directory not in self.agent_dirs:
            self.agent_dirs.append(directory)
    
    def load_global_rules(self, base_path: Optional[Path] = None) -> str:
        """
        공용 규칙 파일 로드 (v3)
        
        GLOBAL.md 또는 CLAUDE.md 파일을 찾아서 로드합니다.
        이 내용은 모든 에이전트의 시스템 프롬프트 앞에 주입됩니다.
        
        Args:
            base_path: 검색 시작 경로 (기본: 현재 디렉토리)
            
        Returns:
            공용 규칙 텍스트 (없으면 빈 문자열)
        """
        if base_path is None:
            base_path = Path.cwd()
        
        for file_name in self.GLOBAL_RULES_FILES:
            path = base_path / file_name
            if path.exists():
                try:
                    content = path.read_text(encoding='utf-8')
                    self._global_rules = content.strip()
                    print(f"공용 규칙 로드됨: {path}")
                    return self._global_rules
                except Exception as e:
                    print(f"공용 규칙 로드 실패: {path} - {e}")
        
        return ""
    
    def _inject_global_rules(self, agent: AgentDefinition) -> None:
        """에이전트 시스템 프롬프트에 공용 규칙 주입"""
        if self._global_rules and agent.system_prompt:
            agent.system_prompt = f"{self._global_rules}\n\n---\n\n{agent.system_prompt}"
    
    @property
    def global_rules(self) -> str:
        """로드된 공용 규칙"""
        return self._global_rules


    
    def load_file(self, file_path: Path) -> Optional[AgentDefinition]:
        """
        단일 .md 파일에서 에이전트 정의 로드
        
        Args:
            file_path: .md 파일 경로
            
        Returns:
            AgentDefinition 또는 None (파싱 실패 시)
        """
        if not file_path.exists() or file_path.suffix != '.md':
            return None
        
        try:
            content = file_path.read_text(encoding='utf-8')
            return self._parse_content(content, file_path)
        except Exception as e:
            print(f"에이전트 파일 로드 실패: {file_path} - {e}")
            return None
    
    def _parse_content(self, content: str, file_path: Path) -> Optional[AgentDefinition]:
        """
        파일 내용에서 frontmatter와 본문 파싱
        
        Format:
        ---
        name: agent-name
        description: When to use this agent
        tools: Read, Grep, Glob
        model: sonnet
        ---
        
        System prompt goes here...
        """
        match = self.FRONTMATTER_PATTERN.match(content)
        if not match:
            return None
        
        frontmatter_text = match.group(1)
        system_prompt = match.group(2).strip()
        
        try:
            frontmatter = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as e:
            print(f"YAML 파싱 실패: {file_path} - {e}")
            return None
        
        # 필수 필드 확인
        if 'name' not in frontmatter or 'description' not in frontmatter:
            print(f"필수 필드 누락 (name, description): {file_path}")
            return None
        
        # tools 필드 파싱 (쉼표 구분 문자열 또는 리스트)
        tools_raw = frontmatter.get('tools', [])
        if isinstance(tools_raw, str):
            tools = [t.strip() for t in tools_raw.split(',')]
        elif isinstance(tools_raw, list):
            tools = tools_raw
        else:
            tools = []
        
        return AgentDefinition(
            name=frontmatter['name'],
            description=frontmatter['description'],
            tools=tools,
            model=frontmatter.get('model', 'inherit'),
            self_improve=frontmatter.get('self_improve', False),  # 자가개선 설정
            system_prompt=system_prompt,
            file_path=file_path
        )

    
    def _parse_orchestrator_content(self, content: str, file_path: Path) -> Optional[OrchestratorDefinition]:
        """
        오케스트레이터 정의 파싱
        
        Format:
        ---
        name: main-orchestrator
        type: orchestrator
        description: 메인 조율 에이전트
        default_agent: file-explorer
        delegate_rules:
          - pattern: "분석|analyze"
            agent: proc-analyzer
            priority: 10
          - pattern: "리뷰|review"
            agent: code-reviewer
        ---
        
        System prompt goes here...
        """
        match = self.FRONTMATTER_PATTERN.match(content)
        if not match:
            return None
        
        frontmatter_text = match.group(1)
        system_prompt = match.group(2).strip()
        
        try:
            frontmatter = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as e:
            print(f"YAML 파싱 실패: {file_path} - {e}")
            return None
        
        # 오케스트레이터 타입 확인
        if frontmatter.get('type') != 'orchestrator':
            return None
        
        # 필수 필드 확인
        if 'name' not in frontmatter:
            print(f"필수 필드 누락 (name): {file_path}")
            return None
        
        # delegate_rules 파싱
        rules_raw = frontmatter.get('delegate_rules', [])
        delegate_rules = []
        
        for rule_data in rules_raw:
            if isinstance(rule_data, dict) and 'pattern' in rule_data and 'agent' in rule_data:
                delegate_rules.append(DelegateRule(
                    pattern=rule_data['pattern'],
                    agent=rule_data['agent'],
                    priority=rule_data.get('priority', 0)
                ))
        
        return OrchestratorDefinition(
            name=frontmatter['name'],
            description=frontmatter.get('description', ''),
            delegate_rules=delegate_rules,
            default_agent=frontmatter.get('default_agent'),
            model=frontmatter.get('model', 'inherit'),
            system_prompt=system_prompt,
            file_path=file_path
        )
    
    def load_orchestrator_file(self, file_path: Path) -> Optional[OrchestratorDefinition]:
        """오케스트레이터 정의 파일 로드"""
        if not file_path.exists() or file_path.suffix != '.md':
            return None
        
        try:
            content = file_path.read_text(encoding='utf-8')
            return self._parse_orchestrator_content(content, file_path)
        except Exception as e:
            print(f"오케스트레이터 파일 로드 실패: {file_path} - {e}")
            return None
    
    def load_all(self, inject_global_rules: bool = True) -> Dict[str, AgentDefinition]:
        """
        모든 디렉토리에서 에이전트 정의 로드
        
        Args:
            inject_global_rules: True이면 GLOBAL.md 내용을 에이전트에 주입
        
        Returns:
            {에이전트 이름: AgentDefinition} 딕셔너리
        """
        self._agents.clear()
        self._orchestrator = None
        
        # v3: 공용 규칙 먼저 로드
        if inject_global_rules:
            for directory in self.agent_dirs:
                if directory.exists():
                    self.load_global_rules(directory.parent)
                    break
        
        for directory in self.agent_dirs:
            if not directory.exists():
                continue
            
            for md_file in directory.glob('*.md'):
                # GLOBAL.md는 스킵 (이미 로드됨)
                if md_file.name.upper() in ('GLOBAL.MD', 'CLAUDE.MD'):
                    continue
                
                # 먼저 오케스트레이터인지 확인
                orch = self.load_orchestrator_file(md_file)
                if orch:
                    self._orchestrator = orch
                    print(f"오케스트레이터 로드됨: {orch.name} ({md_file.name})")
                    continue
                
                # 일반 에이전트 로드
                agent = self.load_file(md_file)
                if agent:
                    # v3: 공용 규칙 주입
                    if inject_global_rules and self._global_rules:
                        self._inject_global_rules(agent)
                    
                    self._agents[agent.name] = agent
                    print(f"에이전트 로드됨: {agent.name} ({md_file.name})")
        
        return self._agents

    
    def get_agent(self, name: str) -> Optional[AgentDefinition]:
        """이름으로 에이전트 찾기"""
        return self._agents.get(name)
    
    def find_matching_agents(self, user_request: str) -> List[AgentDefinition]:
        """사용자 요청에 매칭되는 에이전트 찾기"""
        return [
            agent for agent in self._agents.values()
            if agent.matches_request(user_request)
        ]
    
    def find_agent_by_orchestrator(self, user_request: str) -> Optional[str]:
        """오케스트레이터 규칙으로 에이전트 찾기"""
        if self._orchestrator:
            return self._orchestrator.find_agent_for_request(user_request)
        return None
    
    @property
    def agents(self) -> Dict[str, AgentDefinition]:
        """로드된 모든 에이전트"""
        return self._agents
    
    @property
    def orchestrator(self) -> Optional[OrchestratorDefinition]:
        """로드된 오케스트레이터"""
        return self._orchestrator

