"""
SQL 추출기 설정 모듈

SQLExtractorConfig 클래스를 통해 추출 동작을 설정합니다.
"""

from dataclasses import dataclass, field
from typing import Tuple, Set, FrozenSet


# ============================================================================
# 기본 블랙리스트 상수 정의
# ============================================================================

# 시간/날짜 포맷 키워드 (Oracle, DB2, PostgreSQL 공통)
DEFAULT_TIME_FORMAT_BLACKLIST: FrozenSet[str] = frozenset({
    # 시간 관련
    'HH', 'HH12', 'HH24', 'MI', 'SS', 'SSSSS', 'FF', 'FF1', 'FF2', 'FF3', 'FF4', 'FF5', 'FF6',
    'AM', 'PM', 'A', 'P',
    # 날짜 관련
    'DD', 'DY', 'DAY', 'MM', 'MON', 'MONTH', 'YY', 'YYYY', 'RRRR', 'RR', 'YEAR',
    'DDD', 'WW', 'W', 'Q', 'J',
    # 기타 Oracle 포맷
    'TZH', 'TZM', 'TZR', 'TZD', 'CC', 'SCC', 'SYYYY', 'BC', 'AD',
})

# DB2 특수 레지스터 (CURRENT XXX 형태로 사용됨)
DB2_SPECIAL_REGISTERS: FrozenSet[str] = frozenset({
    'CURRENT', 'DATE', 'TIME', 'TIMESTAMP', 'USER', 'SCHEMA', 'PATH',
    'TIMEZONE', 'CLIENT_ACCTNG', 'CLIENT_APPLNAME', 'CLIENT_USERID', 'CLIENT_WRKSTNNAME',
})

# PostgreSQL 형변환 연산자 뒤에 오는 타입명 (::type 패턴)
# 주의: PostgreSQL에서는 콜론 두 개 (::)가 형변환이므로 :type 형태로 추출되지 않음
# 하지만 일부 Pro*C 코드에서 혼용되는 경우를 대비
POSTGRESQL_TYPE_BLACKLIST: FrozenSet[str] = frozenset({
    'INTEGER', 'INT', 'BIGINT', 'SMALLINT', 'NUMERIC', 'DECIMAL', 'REAL', 'FLOAT',
    'VARCHAR', 'CHAR', 'TEXT', 'BOOLEAN', 'BOOL', 'DATE', 'TIME', 'TIMESTAMP',
    'JSON', 'JSONB', 'UUID', 'BYTEA', 'INTERVAL',
})

# 단일 문자 변수 중 일반적으로 상수로 사용되는 패턴
# 주의: 이 목록은 필요에 따라 확장/축소 가능
SINGLE_CHAR_CONSTANT_BLACKLIST: FrozenSet[str] = frozenset({
    # 일반적으로 NULL, YES/NO, TRUE/FALSE 등의 약어로 사용
    'N', 'Y',
})


@dataclass
class SQLExtractorConfig:
    """SQL 추출기 설정
    
    기존 DecompositionConfig와 호환되는 설정 클래스입니다.
    
    Example:
        # 기본 설정
        config = SQLExtractorConfig()
        
        # 커스텀 블랙리스트 추가
        config = SQLExtractorConfig(
            CUSTOM_HOST_VAR_BLACKLIST={'MY_CONSTANT', 'ANOTHER_KEYWORD'}
        )
        
        # DB2 모드로 설정 (DB2 특수 레지스터 블랙리스트 자동 추가)
        config = SQLExtractorConfig(DBMS_DIALECT="db2")
    """
    
    # 인코딩 설정
    DEFAULT_ENCODING: str = "euc-kr"
    FALLBACK_ENCODING: str = "utf-8"
    
    # SQL 호출 포맷 (기존 호환)
    SQL_CALL_FORMAT: str = 'sql_call("{sql_id}", "{sql_name}");'
    
    # SQL 주석 포맷 (기존 호환)
    SQL_COMMENT_FORMAT: str = "/* sql extracted: SQL_ID:{sql_id}, TYPE:{sql_type}, DESCRIPTION:{desc} */"
    
    # SQL 주석 파일 생성 여부
    GENERATE_SQL_COMMENTED_FILE: bool = True
    
    # 제외할 include 파일
    EXCLUDE_INCLUDES: Tuple[str, ...] = ("afc_svc.h", "afc_bam.h", "atmi.h")
    
    # 건너뛸 함수 목록
    SKIP_FUNCTIONS: Tuple[str, ...] = field(default_factory=tuple)
    
    # DBMS 방언 (oracle, db2, postgresql, common)
    # DB2의 경우 WITH UR, WITH CS 등의 구문을 인식
    DBMS_DIALECT: str = "oracle"
    
    # =========================================================================
    # 호스트 변수 블랙리스트 설정
    # =========================================================================
    
    # 커스텀 블랙리스트 (사용자 정의)
    CUSTOM_HOST_VAR_BLACKLIST: Set[str] = field(default_factory=set)
    
    # 기본 블랙리스트 사용 여부
    USE_TIME_FORMAT_BLACKLIST: bool = True
    USE_DB2_SPECIAL_REGISTERS_BLACKLIST: bool = False  # DB2 dialect 시 자동 활성화
    USE_POSTGRESQL_TYPE_BLACKLIST: bool = False
    USE_SINGLE_CHAR_BLACKLIST: bool = False  # 주의: 실제 단일 문자 변수도 제외될 수 있음
    
    # 문자열 리터럴 내부 호스트 변수 무시 여부
    IGNORE_VARS_IN_STRING_LITERALS: bool = True
    
    def get_combined_blacklist(self) -> Set[str]:
        """활성화된 모든 블랙리스트를 결합하여 반환
        
        Returns:
            호스트 변수로 인식하지 않을 키워드 집합 (대문자)
        """
        combined = set()
        
        if self.USE_TIME_FORMAT_BLACKLIST:
            combined.update(DEFAULT_TIME_FORMAT_BLACKLIST)
        
        # DB2 dialect이면 자동 활성화
        if self.USE_DB2_SPECIAL_REGISTERS_BLACKLIST or self.DBMS_DIALECT.lower() == 'db2':
            combined.update(DB2_SPECIAL_REGISTERS)
        
        if self.USE_POSTGRESQL_TYPE_BLACKLIST or self.DBMS_DIALECT.lower() == 'postgresql':
            combined.update(POSTGRESQL_TYPE_BLACKLIST)
        
        if self.USE_SINGLE_CHAR_BLACKLIST:
            combined.update(SINGLE_CHAR_CONSTANT_BLACKLIST)
        
        # 커스텀 블랙리스트 추가 (대문자로 변환)
        combined.update(kw.upper() for kw in self.CUSTOM_HOST_VAR_BLACKLIST)
        
        return combined

