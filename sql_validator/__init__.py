"""
sql_validator - SQL 검증기 (호환성 레이어)

이 모듈은 이전 경로에서의 import를 지원하기 위한 호환성 레이어입니다.
실제 구현은 validation.sql 패키지에 있습니다.
"""

from validation.sql import *
from validation.sql import __all__
