"""
변환 데이터 타입 정의

Pro*C to Java 변환에 사용되는 데이터 클래스들을 정의합니다.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum


class ConversionStage(Enum):
    """변환 단계"""
    SKELETON = "skeleton"
    FUNCTION = "function"
    COMPLETE = "complete"


@dataclass
class ConversionConfig:
    """
    변환 설정
    
    Attributes:
        package_name: Java 패키지명 (예: com.example.service)
        class_name_suffix: 클래스명 접미사 (예: Service)
        use_spring_annotations: Spring 어노테이션 사용 여부
        mybatis_mapper_package: MyBatis Mapper 패키지
        include_comments: 원본 주석 포함 여부
        generate_test: 테스트 코드 생성 여부
    """
    package_name: str = "com.example.service"
    class_name_suffix: str = "Service"
    use_spring_annotations: bool = True
    mybatis_mapper_package: str = "com.example.mapper"
    include_comments: bool = True
    generate_test: bool = False
    
    # LLM 설정
    temperature: float = 0.3
    max_tokens: int = 4096


@dataclass
class FieldInfo:
    """
    Java 클래스 필드 정보
    
    Pro*C 전역 변수 → Java 필드 변환 시 사용
    """
    name: str
    java_type: str
    original_c_type: str
    description: Optional[str] = None
    is_host_variable: bool = False
    default_value: Optional[str] = None


@dataclass
class MethodSignature:
    """
    Java 메서드 시그니처
    
    Pro*C 함수 프로토타입 → Java 메서드 시그니처 변환 시 사용
    """
    name: str
    java_name: str  # camelCase 변환된 이름
    return_type: str
    parameters: List[str]
    original_prototype: str
    is_private: bool = True
    description: Optional[str] = None


@dataclass
class SqlReference:
    """
    SQL 참조 정보
    
    함수 내에서 사용되는 SQL 문에 대한 참조
    """
    sql_id: str
    sql_type: str  # SELECT, INSERT, UPDATE, DELETE
    table_names: List[str]
    mybatis_mapper_method: Optional[str] = None


@dataclass
class SkeletonResult:
    """
    클래스 스켈레톤 생성 결과
    
    1단계 변환 결과물로, 클래스 구조만 포함
    """
    class_name: str
    package_name: str
    imports: List[str] = field(default_factory=list)
    fields: List[FieldInfo] = field(default_factory=list)
    method_signatures: List[MethodSignature] = field(default_factory=list)
    java_code: str = ""
    
    # 메타데이터
    source_file: str = ""
    generated_at: str = ""


@dataclass
class FunctionConversionResult:
    """
    개별 함수 변환 결과
    
    2단계 변환 결과물로, 함수 본문 구현 포함
    """
    original_name: str
    java_method_name: str
    java_code: str
    sql_references: List[SqlReference] = field(default_factory=list)
    called_functions: List[str] = field(default_factory=list)
    
    # 변환 품질 정보
    confidence_score: float = 0.0
    warnings: List[str] = field(default_factory=list)


@dataclass
class ConversionResult:
    """
    전체 변환 결과
    
    스켈레톤 + 모든 함수 변환 결과를 포함
    """
    skeleton: SkeletonResult
    functions: List[FunctionConversionResult] = field(default_factory=list)
    full_java_code: str = ""
    
    # 변환 통계
    total_functions: int = 0
    converted_functions: int = 0
    skipped_functions: List[str] = field(default_factory=list)
    
    # 오류 정보
    errors: List[str] = field(default_factory=list)
    
    def is_complete(self) -> bool:
        """모든 함수가 변환되었는지 확인"""
        return self.converted_functions == self.total_functions
    
    def success_rate(self) -> float:
        """변환 성공률"""
        if self.total_functions == 0:
            return 1.0
        return self.converted_functions / self.total_functions


@dataclass
class PromptContext:
    """
    프롬프트 생성 컨텍스트
    
    프롬프트 빌더에서 사용하는 컨텍스트 정보
    """
    source_file: str
    metadata: Dict[str, Any]
    config: ConversionConfig
    
    # 선택적 컨텍스트
    skeleton_result: Optional[SkeletonResult] = None
    previous_functions: List[FunctionConversionResult] = field(default_factory=list)
