"""
translation_merge 모듈 데이터 타입 정의

Pro*C → Java 변환 결과물 병합을 위한 데이터 클래스들.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class MethodTranslation:
    """개별 메소드 변환 결과.
    
    Attributes:
        name: 추출할 메소드 이름
        llm_response: LLM 응답 전체 텍스트 (추가 import, helper 메소드 포함 가능)
    """
    name: str
    llm_response: str


@dataclass
class ExtractedMethod:
    """파싱된 메소드 정보.
    
    Attributes:
        name: 메소드 이름
        signature: 메소드 시그니처 (접근제한자, 반환타입, 이름, 파라미터)
        body: 메소드 전체 코드 (시그니처 + 본문)
        start_line: 원본 코드에서의 시작 라인 (optional)
        end_line: 원본 코드에서의 종료 라인 (optional)
    """
    name: str
    signature: str
    body: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None


@dataclass
class MergeResult:
    """병합 결과.
    
    Attributes:
        merged_code: 최종 병합된 Java 클래스 코드
        imports: 수집된 모든 import 목록 (중복 제거됨)
        methods: 병합된 메소드 이름 목록
        warnings: 병합 중 발생한 경고 메시지
    """
    merged_code: str
    imports: List[str] = field(default_factory=list)
    methods: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
