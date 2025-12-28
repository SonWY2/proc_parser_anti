"""
자가개선 체크리스트 시스템

에이전트 실행 중 반복 발생하는 이슈를 자동으로 체크리스트로 변환합니다.
"""

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any, TYPE_CHECKING
import yaml
import json

if TYPE_CHECKING:
    from .agent_loader import AgentDefinition


@dataclass
class Issue:
    """발생한 이슈"""
    agent: str
    description: str
    context: str = ""           # 어떤 상황에서 발생했는지
    step_name: str = ""         # 워크플로우 단계명
    input_snippet: str = ""     # 입력 코드 일부
    timestamp: str = ""
    resolved: bool = False
    resolution: str = ""        # 해결 방법
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'agent': self.agent,
            'description': self.description,
            'context': self.context,
            'step_name': self.step_name,
            'input_snippet': self.input_snippet,
            'timestamp': self.timestamp,
            'resolved': self.resolved,
            'resolution': self.resolution
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Issue':
        return cls(**data)


@dataclass
class ChecklistItem:
    """체크리스트 항목"""
    id: str
    issue: str                  # 원본 이슈 설명
    check: str                  # 체크할 내용
    frequency: int = 1          # 발생 횟수
    example: str = ""           # 예시 코드
    added_on: str = ""
    auto_generated: bool = True
    
    def __post_init__(self):
        if not self.added_on:
            self.added_on = datetime.now().strftime("%Y-%m-%d")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'issue': self.issue,
            'check': self.check,
            'frequency': self.frequency,
            'example': self.example,
            'added_on': self.added_on,
            'auto_generated': self.auto_generated
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChecklistItem':
        return cls(**data)


class SelfImprovingChecklist:
    """
    자가개선 체크리스트 시스템
    
    - 반복 발생하는 이슈를 자동으로 체크리스트로 변환
    - 에이전트 프롬프트에 체크리스트 자동 주입
    - 에이전트/워크플로우 레벨에서 on/off 제어
    """
    
    THRESHOLD = 3  # 3회 이상 발생 시 체크리스트 승격
    
    def __init__(self, base_dir: str = ".agents/checklists"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # 이슈 로그 (메모리)
        self.issues: Dict[str, List[Issue]] = {}
        
        # 체크리스트 (영구 저장)
        self.checklists: Dict[str, List[ChecklistItem]] = {}
        
        self._load_all()
    
    def _load_all(self) -> None:
        """저장된 체크리스트 및 이슈 로드"""
        for path in self.base_dir.glob("*.yaml"):
            agent = path.stem
            try:
                data = yaml.safe_load(path.read_text(encoding='utf-8'))
                
                # 체크리스트 로드
                self.checklists[agent] = [
                    ChecklistItem.from_dict(item) 
                    for item in data.get('checklist', [])
                ]
                
                # 미해결 이슈 로드
                self.issues[agent] = [
                    Issue.from_dict(item)
                    for item in data.get('pending_issues', [])
                ]
            except Exception as e:
                print(f"[SelfImprove] 로드 실패: {path} - {e}")
    
    def _save(self, agent: str) -> None:
        """에이전트별 체크리스트 저장"""
        path = self.base_dir / f"{agent}.yaml"
        
        data = {
            'agent': agent,
            'last_updated': datetime.now().isoformat(),
            'checklist': [
                item.to_dict() for item in self.checklists.get(agent, [])
            ],
            'pending_issues': [
                issue.to_dict() for issue in self.issues.get(agent, [])
                if not issue.resolved
            ]
        }
        
        path.write_text(
            yaml.dump(data, allow_unicode=True, default_flow_style=False),
            encoding='utf-8'
        )
    
    def is_enabled(
        self, 
        agent_def: Optional['AgentDefinition'] = None,
        workflow_step_config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        자가개선 활성화 여부 확인
        
        우선순위: 워크플로우 설정 > 에이전트 설정 > 기본값(False)
        """
        # 기본값
        enabled = False
        
        # 에이전트 레벨 설정 확인
        if agent_def and hasattr(agent_def, 'self_improve'):
            enabled = agent_def.self_improve
        
        # 워크플로우 레벨 오버라이드
        if workflow_step_config and 'self_improve' in workflow_step_config:
            enabled = workflow_step_config['self_improve']
        
        return enabled
    
    def log_issue(self, issue: Issue) -> Optional[ChecklistItem]:
        """
        이슈 기록 및 패턴 감지
        
        Args:
            issue: 발생한 이슈
            
        Returns:
            새로 생성된 체크리스트 항목 (임계값 도달 시)
        """
        if issue.agent not in self.issues:
            self.issues[issue.agent] = []
        
        self.issues[issue.agent].append(issue)
        
        # 패턴 감지: 유사 이슈 개수 확인
        similar_count = self._count_similar_issues(issue)
        
        if similar_count >= self.THRESHOLD:
            new_item = self._promote_to_checklist(issue, similar_count)
            self._save(issue.agent)
            return new_item
        
        self._save(issue.agent)
        return None
    
    def _count_similar_issues(self, issue: Issue) -> int:
        """유사한 이슈 개수 카운트"""
        count = 0
        for past_issue in self.issues.get(issue.agent, []):
            if self._is_similar(issue.description, past_issue.description):
                count += 1
        return count
    
    def _is_similar(self, desc1: str, desc2: str) -> bool:
        """두 이슈가 유사한지 판단 (키워드 기반)"""
        words1 = set(desc1.lower().split())
        words2 = set(desc2.lower().split())
        
        if not words1 or not words2:
            return False
        
        overlap = len(words1 & words2) / min(len(words1), len(words2))
        return overlap > 0.5
    
    def _promote_to_checklist(self, issue: Issue, frequency: int) -> ChecklistItem:
        """이슈를 체크리스트 항목으로 승격"""
        if issue.agent not in self.checklists:
            self.checklists[issue.agent] = []
        
        # 이미 유사한 체크리스트 항목이 있는지 확인
        for item in self.checklists[issue.agent]:
            if self._is_similar(item.issue, issue.description):
                item.frequency = frequency
                return item
        
        # 새 항목 생성
        new_id = f"CHK-{len(self.checklists[issue.agent]) + 1:03d}"
        
        new_item = ChecklistItem(
            id=new_id,
            issue=issue.description,
            check=f"확인: {issue.description}",
            frequency=frequency,
            example=issue.input_snippet,
            auto_generated=True
        )
        
        self.checklists[issue.agent].append(new_item)
        print(f"[SelfImprove] 새 체크리스트 항목 추가: {new_item.check}")
        
        return new_item
    
    def get_checklist_prompt(self, agent: str) -> str:
        """
        에이전트 프롬프트에 주입할 체크리스트 텍스트
        
        Args:
            agent: 에이전트 이름
            
        Returns:
            마크다운 형식의 체크리스트 텍스트
        """
        items = self.checklists.get(agent, [])
        if not items:
            return ""
        
        lines = [
            "",
            "## ⚠️ 자동 생성 체크리스트 (과거 실패 사례 기반)",
            "",
            "> 다음 항목들은 과거 반복 발생한 이슈입니다. 작업 전에 확인하세요.",
            ""
        ]
        
        for item in items:
            lines.append(f"- [ ] **{item.check}** (발생 {item.frequency}회)")
            if item.example:
                # 예시가 있으면 코드 블록으로 표시
                example_short = item.example[:100] + "..." if len(item.example) > 100 else item.example
                lines.append(f"      ```")
                lines.append(f"      {example_short}")
                lines.append(f"      ```")
        
        lines.append("")
        return "\n".join(lines)
    
    def resolve_issue(
        self, 
        agent: str, 
        issue_description: str, 
        resolution: str
    ) -> int:
        """
        이슈 해결 기록
        
        Args:
            agent: 에이전트 이름
            issue_description: 이슈 설명 (유사 매칭)
            resolution: 해결 방법
            
        Returns:
            해결된 이슈 개수
        """
        resolved_count = 0
        
        for issue in self.issues.get(agent, []):
            if not issue.resolved and self._is_similar(issue.description, issue_description):
                issue.resolved = True
                issue.resolution = resolution
                resolved_count += 1
        
        if resolved_count > 0:
            self._save(agent)
        
        return resolved_count
    
    def get_statistics(self, agent: Optional[str] = None) -> Dict[str, Any]:
        """통계 조회"""
        if agent:
            return {
                'agent': agent,
                'total_issues': len(self.issues.get(agent, [])),
                'resolved_issues': sum(1 for i in self.issues.get(agent, []) if i.resolved),
                'checklist_items': len(self.checklists.get(agent, []))
            }
        
        return {
            'total_agents': len(set(self.issues.keys()) | set(self.checklists.keys())),
            'total_issues': sum(len(issues) for issues in self.issues.values()),
            'total_checklist_items': sum(len(items) for items in self.checklists.values())
        }
    
    def add_manual_check(
        self, 
        agent: str, 
        check: str, 
        example: str = ""
    ) -> ChecklistItem:
        """수동으로 체크리스트 항목 추가"""
        if agent not in self.checklists:
            self.checklists[agent] = []
        
        new_id = f"MAN-{len([i for i in self.checklists[agent] if not i.auto_generated]) + 1:03d}"
        
        new_item = ChecklistItem(
            id=new_id,
            issue="수동 추가",
            check=check,
            example=example,
            auto_generated=False
        )
        
        self.checklists[agent].append(new_item)
        self._save(agent)
        
        return new_item
    
    def clear_checklist(self, agent: str) -> int:
        """에이전트 체크리스트 초기화"""
        count = len(self.checklists.get(agent, []))
        self.checklists[agent] = []
        self._save(agent)
        return count
    
    # ========================================
    # 훅 통합 메서드
    # ========================================
    
    def create_step_end_hook(self, agent_loader: Optional[Any] = None):
        """
        STEP_END 훅 생성: 실패 시 이슈 자동 수집
        
        Args:
            agent_loader: AgentLoader 인스턴스 (self_improve 설정 확인용)
        """
        def hook_callback(ctx) -> None:
            """단계 종료 시 이슈 수집"""
            from .hooks import HookContext
            
            # 에이전트 정의 가져오기
            agent_def = None
            if agent_loader and ctx.agent_name:
                agent_def = agent_loader.get_agent(ctx.agent_name)
            
            # 워크플로우 단계 설정 가져오기
            step_config = ctx.data.get('step_config', {})
            
            # 자가개선 활성화 확인
            if not self.is_enabled(agent_def, step_config):
                return None
            
            # 오류가 있는 경우만 이슈 수집
            if ctx.error:
                issue = Issue(
                    agent=ctx.agent_name or "unknown",
                    description=ctx.error,
                    context=f"Workflow: {ctx.workflow_name}, Step: {ctx.step_name}",
                    step_name=ctx.step_name or "",
                    input_snippet=ctx.data.get('input_snippet', '')[:200]
                )
                
                new_item = self.log_issue(issue)
                if new_item:
                    print(f"[SelfImprove] 체크리스트 승격: {new_item.check}")
            
            return None
        
        return hook_callback
    
    def create_step_start_hook(self, agent_loader: Optional[Any] = None):
        """
        STEP_START 훅 생성: 체크리스트 프롬프트 주입
        
        Args:
            agent_loader: AgentLoader 인스턴스
        """
        def hook_callback(ctx) -> None:
            """단계 시작 시 체크리스트 주입"""
            
            # 에이전트 정의 가져오기
            agent_def = None
            if agent_loader and ctx.agent_name:
                agent_def = agent_loader.get_agent(ctx.agent_name)
            
            # 워크플로우 단계 설정 가져오기
            step_config = ctx.data.get('step_config', {})
            
            # 자가개선 활성화 확인
            if not self.is_enabled(agent_def, step_config):
                return None
            
            # 체크리스트 프롬프트 생성 및 주입
            if ctx.agent_name:
                checklist_prompt = self.get_checklist_prompt(ctx.agent_name)
                if checklist_prompt:
                    ctx.data['injected_checklist'] = checklist_prompt
                    print(f"[SelfImprove] 체크리스트 주입: {ctx.agent_name}")
            
            return None
        
        return hook_callback
    
    def setup_hooks(self, hook_registry, agent_loader: Optional[Any] = None) -> None:
        """
        훅 레지스트리에 자가개선 훅 등록
        
        Args:
            hook_registry: HookRegistry 인스턴스
            agent_loader: AgentLoader 인스턴스
            
        Usage:
            from agent_system import HookRegistry, SelfImprovingChecklist, AgentLoader
            
            hooks = HookRegistry()
            loader = AgentLoader([Path(".agents")])
            si = SelfImprovingChecklist()
            
            si.setup_hooks(hooks, loader)
        """
        from .hooks import HookEvent
        
        # STEP_END: 이슈 수집
        hook_registry.register(
            HookEvent.STEP_END,
            self.create_step_end_hook(agent_loader)
        )
        
        # STEP_START: 체크리스트 주입
        hook_registry.register(
            HookEvent.STEP_START,
            self.create_step_start_hook(agent_loader)
        )
        
        print("[SelfImprove] 훅 등록 완료")

