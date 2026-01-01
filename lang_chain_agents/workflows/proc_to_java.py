"""
Pro*C to Java 변환 워크플로우 (정적)

미리 정의된 6단계 변환 파이프라인입니다.
"""
from .base import BaseWorkflow, WorkflowStep


# Pro*C → Java 변환 워크플로우 정의
PROC_TO_JAVA_WORKFLOW = BaseWorkflow(
    name="proc_to_java",
    description="Pro*C 코드를 Java Spring Boot + MyBatis로 변환하는 전체 파이프라인",
    steps=[
        # 1단계: 종속성 분석
        WorkflowStep(
            name="analyze_dependencies",
            agent="dependency_analyst",
            task_template="""${target_dir} 디렉토리의 Pro*C 프로젝트를 분석하세요.

작업:
1. 모든 .pc 및 .h 파일 탐색
2. #include 관계 분석
3. 공유 헤더 식별 (2개 이상 .pc에서 사용되는 헤더)
4. 종속성 순서 결정 (위상 정렬)

결과를 마크다운으로 정리하세요.""",
            next_step="parse_code",
        ),
        
        # 2단계: 코드 파싱
        WorkflowStep(
            name="parse_code",
            agent="parsing_agent",
            task_template="""이전 종속성 분석 결과를 참고하여 Pro*C 코드를 파싱하세요.

작업:
1. 각 .pc 파일에서 함수, 전역 변수, 매크로, 구조체 추출
2. 타입 정보 및 시그니처 기록
3. 공유 헤더의 공통 요소 식별

파싱 결과를 마크다운 테이블로 정리하세요.""",
            next_step="extract_sql",
        ),
        
        # 3단계: SQL 추출
        WorkflowStep(
            name="extract_sql",
            agent="sql_analyst",
            task_template="""Pro*C 코드에서 EXEC SQL 구문을 추출하고 MyBatis 형식으로 변환하세요.

작업:
1. EXEC SQL 블록 추출
2. 호스트 변수 :var → #{var} 변환 (camelCase)
3. 커서 패턴 분석
4. MyBatis Mapper XML 형식으로 전처리

SQL 매핑 결과를 정리하세요.""",
            next_step="build_context",
        ),
        
        # 4단계: 컨텍스트 생성
        WorkflowStep(
            name="build_context",
            agent="context_engineer",
            task_template="""파싱 결과와 SQL 분석 결과를 통합하여 변환 컨텍스트를 생성하세요.

작업:
1. 클래스 정보 매핑 (C 파일 → Java 클래스)
2. 메서드 매핑 (C 함수 → Java 메서드)
3. DTO 클래스 정의 (C 구조체 → Java 클래스)
4. SQL Mapper 정보 정리

변환에 필요한 핵심 정보만 간결하게 정리하세요.""",
            next_step="transform_code",
            checkpoint=True,  # 변환 전 체크포인트
        ),
        
        # 5단계: 코드 변환
        WorkflowStep(
            name="transform_code",
            agent="transformer",
            task_template="""컨텍스트를 기반으로 Java 코드를 생성하세요.

변환 순서:
1. 공통 DTO 클래스 (com.example.common.dto)
2. 공통 유틸리티 (com.example.common.util)
3. 개별 Service 클래스
4. MyBatis Mapper XML

출력 디렉토리: ${output_dir}

Spring Boot + Lombok + MyBatis 규칙을 준수하세요.""",
            next_step="validate_result",
        ),
        
        # 6단계: 결과 검증
        WorkflowStep(
            name="validate_result",
            agent="critic",
            task_template="""생성된 Java 코드의 품질을 검증하세요.

검증 항목:
1. Java 문법 오류 여부
2. 모든 함수가 변환되었는지
3. SQL이 올바르게 변환되었는지
4. 공유 컴포넌트 중복 여부
5. import 문 완전성

PASSED/FAILED로 판정하고 개선사항을 제시하세요.""",
            next_step=None,  # 종료
            quality_gate="critic",
        ),
    ],
)


# 간소화된 워크플로우 (3단계)
PROC_TO_JAVA_SIMPLE_WORKFLOW = BaseWorkflow(
    name="proc_to_java_simple",
    description="Pro*C to Java 간소화 변환 (분석 → 변환 → 검증)",
    steps=[
        WorkflowStep(
            name="analyze",
            agent="dependency_analyst",
            task_template="${target_dir}의 Pro*C 파일을 분석하고 변환 컨텍스트를 생성하세요.",
            next_step="transform",
        ),
        WorkflowStep(
            name="transform",
            agent="transformer",
            task_template="분석 결과를 기반으로 Java 코드를 생성하세요. 출력: ${output_dir}",
            next_step="validate",
        ),
        WorkflowStep(
            name="validate",
            agent="critic",
            task_template="생성된 Java 코드를 검증하세요.",
            next_step=None,
        ),
    ],
)
