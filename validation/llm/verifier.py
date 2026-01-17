"""
메인 LLMVerifier 클래스

검증 파이프라인을 관리하고 플러그인을 통해 검증을 수행합니다.
"""

from typing import Any, List, Optional, Dict
from pathlib import Path
import yaml

from .types import VerificationContext, VerificationResult
from .plugins import load_plugins_by_phase, PluginPhase


class LLMVerifier:
    """LLM 기반 검증 오케스트레이터
    
    플러그인 시스템을 통해 검증 파이프라인을 관리합니다.
    
    Example:
        verifier = LLMVerifier()
        result = verifier.verify(
            stage="sql_extraction",
            source=proc_code,
            result=extracted_elements
        )
        
        if result.has_errors():
            for err in result.get_errors():
                print(f"Error: {err.message}")
    """
    
    def __init__(self, enabled_plugins: Optional[List[str]] = None):
        """
        Args:
            enabled_plugins: 활성화할 플러그인 이름들 (None이면 전체)
        """
        self.enabled_plugins = enabled_plugins
    
    def verify(
        self,
        stage: str,
        source: str,
        result: Any,
        checklist_path: Optional[str] = None
    ) -> VerificationResult:
        """변환 결과 검증
        
        Args:
            stage: 검증 단계 ("sql_extraction", "function_parsing", etc.)
            source: 원본 소스 코드
            result: 변환 결과
            checklist_path: 체크리스트 YAML 경로 (None이면 기본 체크리스트)
            
        Returns:
            VerificationResult: 검증 결과
        """
        # 1. 컨텍스트 생성
        context = VerificationContext(
            stage=stage,
            source=source,
            result=result,
            checklist_path=checklist_path or self._get_default_checklist(stage)
        )
        
        # 2. PRE_VERIFY 플러그인 실행 (정적 체크, 샘플링)
        for plugin in load_plugins_by_phase(PluginPhase.PRE_VERIFY, stage, self.enabled_plugins):
            context = plugin.process(context)
        
        # 3. VERIFY 플러그인 실행 (LLM 검증)
        for plugin in load_plugins_by_phase(PluginPhase.VERIFY, stage, self.enabled_plugins):
            context = plugin.process(context)
        
        # 4. 결과 생성
        verification_result = VerificationResult.from_context(context)
        
        # 5. POST_VERIFY 플러그인 실행 (리포트 생성)
        for plugin in load_plugins_by_phase(PluginPhase.POST_VERIFY, stage, self.enabled_plugins):
            verification_result = plugin.process_result(verification_result)
        
        return verification_result
    
    def verify_batch(
        self,
        stage: str,
        items: List[Dict[str, Any]],
        checklist_path: Optional[str] = None
    ) -> List[VerificationResult]:
        """배치 검증
        
        Args:
            stage: 검증 단계
            items: [{"source": str, "result": Any}, ...] 형태의 리스트
            checklist_path: 체크리스트 경로
            
        Returns:
            검증 결과 리스트
        """
        results = []
        for item in items:
            result = self.verify(
                stage=stage,
                source=item['source'],
                result=item['result'],
                checklist_path=checklist_path
            )
            results.append(result)
        return results
    
    def _get_default_checklist(self, stage: str) -> Optional[str]:
        """기본 체크리스트 경로 반환"""
        checklist_dir = Path(__file__).parent / "checklists"
        checklist_file = checklist_dir / f"{stage}.yaml"
        
        if checklist_file.exists():
            return str(checklist_file)
        return None
    
    def load_checklist(self, path: str) -> Dict[str, Any]:
        """체크리스트 YAML 로드
        
        Args:
            path: YAML 파일 경로
            
        Returns:
            체크리스트 딕셔너리
        """
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def get_available_stages(self) -> List[str]:
        """사용 가능한 검증 단계 목록"""
        return [
            "sql_extraction",
            "function_parsing",
            "header_parsing",
            "translation_merge",
        ]
