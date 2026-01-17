"""
proc_parser - Pro*C 파서 모듈 (호환성 레이어)

이 모듈은 이전 경로에서의 import를 지원하기 위한 호환성 레이어입니다.
실제 구현은 parsing.core 패키지에 있습니다.

Usage:
    # 기존 방식 (계속 동작)
    from proc_parser import ProCParser
    
    # 새 방식 (권장)
    from parsing.core import ProCParser
"""

# 새로운 위치에서 모든 exports 가져오기
from parsing.core import *
from parsing.core import __all__
