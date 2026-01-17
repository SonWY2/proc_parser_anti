"""
sql_extractor - SQL 추출 모듈 (호환성 레이어)

이 모듈은 이전 경로에서의 import를 지원하기 위한 호환성 레이어입니다.
실제 구현은 parsing.sql 패키지에 있습니다.

Usage:
    # 기존 방식 (계속 동작)
    from sql_extractor import SQLExtractor
    
    # 새 방식 (권장)
    from parsing.sql import SQLExtractor
"""

from parsing.sql import *
from parsing.sql import __all__
