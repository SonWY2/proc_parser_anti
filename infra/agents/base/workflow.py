"""
워크플로우 시스템

에이전트들을 순차/병렬로 조합하여 복잡한 작업을 자동화합니다.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, TYPE_CHECKING
from pathlib import Path
from datetime import datetime
import json

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

if TYPE_CHECKING:
    from .orchestrator import Orchestrator


@dataclass
class WorkflowStep:
    """워크플로우 단계"""
    name: str
    agent: str
    task: str
    condition: Optional[str] = None      # 실행 조건 (이전 결과 기반)
    on_success: Optional[str] = None     # 성공 시 다음 단계
    on_failure: Optional[str] = None     # 실패 시 다음 단계
    timeout: Optional[int] = None        # 타임아웃 (초)
    retry: int = 0                       # 재시도 횟수
    self_improve: Optional[bool] = None  # 자가개선 (None=에이전트 설정 따름)



@dataclass
class WorkflowResult:
    """워크플로우 실행 결과"""
    success: bool
    workflow_name: str
    steps_executed: List[str]
    outputs: Dict[str, str]
    errors: Dict[str, str]
    total_time: float = 0.0
    
    def summary(self) -> str:
        """결과 요약"""
        status = "✅ 성공" if self.success else "❌ 실패"
        lines = [
            f"{status}: {self.workflow_name}",
            f"실행된 단계: {len(self.steps_executed)}개",
            f"총 소요 시간: {self.total_time:.2f}초",
        ]
        
        if self.errors:
            lines.append(f"오류: {len(self.errors)}개")
            for step, error in self.errors.items():
                lines.append(f"  - {step}: {error}")
        
        return '\n'.join(lines)


@dataclass
class WorkflowDefinition:
    """워크플로우 정의"""
    name: str
    description: str = ""
    steps: List[WorkflowStep] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> 'WorkflowDefinition':
        """딕셔너리에서 워크플로우 정의 생성"""
        steps = [
            WorkflowStep(
                name=step['name'],
                agent=step['agent'],
                task=step['task'],
                condition=step.get('condition'),
                on_success=step.get('on_success'),
                on_failure=step.get('on_failure'),
                timeout=step.get('timeout'),
                retry=step.get('retry', 0)
            )
            for step in data.get('steps', [])
        ]
        
        return cls(
            name=name,
            description=data.get('description', ''),
            steps=steps,
            variables=data.get('variables', {})
        )


MAX_PARALLEL_AGENTS = 10  # 최대 병렬 에이전트 수


@dataclass
class ParallelGroup:
    """병렬 실행 단계 그룹"""
    name: str
    steps: List[str]              # 병렬 실행할 단계 이름들 (최대 10개)
    wait_all: bool = True         # 모든 단계 완료 대기
    fail_fast: bool = False       # 하나 실패 시 즉시 중단
    on_success: Optional[str] = None
    on_failure: Optional[str] = None


class WorkflowEngine:
    """워크플로우 실행 엔진 (v3)"""
    
    def __init__(self, orchestrator: 'Orchestrator'):
        self.orchestrator = orchestrator
        self.workflows: Dict[str, WorkflowDefinition] = {}
        
        # v3: 새 컴포넌트 통합
        from .hooks import HookRegistry
        from .validator import QualityGateValidator
        from .checkpoint import CheckpointManager
        from .file_mediator import FileMediator
        
        self.hooks = HookRegistry()
        self.validator = QualityGateValidator(orchestrator)
        self.checkpoint_manager = CheckpointManager()
        self.file_mediator = FileMediator()
        
        # 병렬 그룹
        self.parallel_groups: Dict[str, ParallelGroup] = {}
        
        # 작업 큐 (10개 초과 시)
        self._pending_queue: List[Dict[str, Any]] = []

    
    def load_from_file(self, file_path: str) -> int:
        """
        파일에서 워크플로우 로드
        
        Args:
            file_path: YAML 또는 JSON 파일 경로
            
        Returns:
            로드된 워크플로우 수
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")
        
        content = path.read_text(encoding='utf-8')
        
        if path.suffix in ('.yaml', '.yml'):
            if not HAS_YAML:
                raise ImportError("YAML 파일을 읽으려면 PyYAML을 설치하세요: pip install pyyaml")
            data = yaml.safe_load(content)
        else:
            data = json.loads(content)
        
        count = 0
        for wf_name, wf_data in data.get('workflows', {}).items():
            self.workflows[wf_name] = WorkflowDefinition.from_dict(wf_name, wf_data)
            count += 1
        
        return count
    
    def load_from_directory(self, directory: str, pattern: str = "*.yaml") -> int:
        """
        디렉토리에서 모든 워크플로우 파일 로드
        
        Args:
            directory: 디렉토리 경로
            pattern: 파일 패턴
            
        Returns:
            로드된 총 워크플로우 수
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            return 0
        
        total = 0
        for file_path in dir_path.glob(pattern):
            try:
                total += self.load_from_file(str(file_path))
            except Exception as e:
                print(f"워크플로우 로드 실패: {file_path} - {e}")
        
        return total
    
    def register(self, workflow: WorkflowDefinition) -> None:
        """워크플로우 등록"""
        self.workflows[workflow.name] = workflow
    
    def list_workflows(self) -> List[Dict[str, str]]:
        """등록된 워크플로우 목록"""
        return [
            {'name': wf.name, 'description': wf.description, 'steps': len(wf.steps)}
            for wf in self.workflows.values()
        ]
    
    def execute(
        self, 
        workflow_name: str, 
        context: Optional[Dict[str, Any]] = None,
        dry_run: bool = False
    ) -> WorkflowResult:
        """
        워크플로우 실행
        
        Args:
            workflow_name: 실행할 워크플로우 이름
            context: 초기 컨텍스트 변수
            dry_run: True면 실제 실행 없이 검증만
            
        Returns:
            워크플로우 실행 결과
        """
        import time
        start_time = time.time()
        
        workflow = self.workflows.get(workflow_name)
        if not workflow:
            return WorkflowResult(
                success=False,
                workflow_name=workflow_name,
                steps_executed=[],
                outputs={},
                errors={"_init": f"워크플로우를 찾을 수 없습니다: {workflow_name}"}
            )
        
        if not workflow.steps:
            return WorkflowResult(
                success=False,
                workflow_name=workflow_name,
                steps_executed=[],
                outputs={},
                errors={"_init": "워크플로우에 단계가 없습니다"}
            )
        
        # 컨텍스트 초기화
        ctx = {**workflow.variables, **(context or {})}
        outputs: Dict[str, str] = {}
        errors: Dict[str, str] = {}
        executed: List[str] = []
        
        # 단계 맵 생성
        step_map = {s.name: s for s in workflow.steps}
        current_step_name: Optional[str] = workflow.steps[0].name
        
        while current_step_name:
            step = step_map.get(current_step_name)
            if not step:
                errors[current_step_name] = f"단계를 찾을 수 없습니다: {current_step_name}"
                break
            
            # 조건 확인
            if step.condition and not self._evaluate_condition(step.condition, ctx, outputs):
                print(f"[워크플로우] 조건 미충족, 스킵: {step.name}")
                current_step_name = step.on_success  # 조건 미충족 시 다음으로
                continue
            
            # dry run 모드
            if dry_run:
                print(f"[DRY-RUN] 단계: {step.name} -> 에이전트: {step.agent}")
                executed.append(step.name)
                current_step_name = step.on_success
                continue
            
            # 태스크 템플릿 렌더링
            task = self._render_template(step.task, ctx, outputs)
            
            # 에이전트 실행 (재시도 지원)
            success = False
            last_error = ""
            
            for attempt in range(step.retry + 1):
                if attempt > 0:
                    print(f"[워크플로우] 재시도 {attempt}/{step.retry}: {step.name}")
                
                result = self.orchestrator.delegate(step.agent, task)
                
                if result.success:
                    outputs[step.name] = result.output
                    ctx[step.name] = result.output
                    success = True
                    break
                else:
                    last_error = result.error or "Unknown error"
            
            executed.append(step.name)
            
            if success:
                current_step_name = step.on_success
            else:
                errors[step.name] = last_error
                current_step_name = step.on_failure
        
        return WorkflowResult(
            success=len(errors) == 0,
            workflow_name=workflow_name,
            steps_executed=executed,
            outputs=outputs,
            errors=errors,
            total_time=time.time() - start_time
        )
    
    def _render_template(
        self, 
        template: str, 
        context: Dict[str, Any], 
        outputs: Dict[str, str]
    ) -> str:
        """태스크 템플릿 렌더링"""
        result = template
        
        # ${변수명} 형식 치환
        for key, value in {**context, **outputs}.items():
            result = result.replace(f"${{{key}}}", str(value))
        
        return result
    
    def _evaluate_condition(
        self, 
        condition: str, 
        context: Dict[str, Any], 
        outputs: Dict[str, str]
    ) -> bool:
        """조건 평가 (간단한 문자열 포함 체크)"""
        # 예: "find_files in outputs" 또는 "success == true"
        try:
            # 간단한 존재 체크
            if ' in ' in condition:
                parts = condition.split(' in ')
                key = parts[0].strip()
                container = parts[1].strip()
                
                if container == 'outputs':
                    return key in outputs
                elif container == 'context':
                    return key in context
            
            # 변수 존재 체크
            if condition.startswith('exists:'):
                key = condition.replace('exists:', '').strip()
                return key in outputs or key in context
            
            # 기본: True
            return True
        except Exception:
            return True
    
    def create_workflow(
        self,
        name: str,
        steps: List[Dict[str, Any]],
        description: str = ""
    ) -> WorkflowDefinition:
        """
        프로그래밍 방식으로 워크플로우 생성
        
        Args:
            name: 워크플로우 이름
            steps: 단계 정의 목록
            description: 설명
            
        Returns:
            생성된 워크플로우 정의
        """
        workflow = WorkflowDefinition.from_dict(name, {
            'description': description,
            'steps': steps
        })
        self.register(workflow)
        return workflow
