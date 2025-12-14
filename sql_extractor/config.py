"""
SQL 추출기 설정 모듈

SQLExtractorConfig 클래스를 통해 추출 동작을 설정합니다.
"""

from dataclasses import dataclass, field
from typing import Tuple


@dataclass
class SQLExtractorConfig:
    """SQL 추출기 설정
    
    기존 DecompositionConfig와 호환되는 설정 클래스입니다.
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
    
    # DBMS 방언 (oracle, db2, common)
    # DB2의 경우 WITH UR, WITH CS 등의 구문을 인식
    DBMS_DIALECT: str = "oracle"
