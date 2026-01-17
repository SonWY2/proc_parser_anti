"""
proc_parser 플러그인 패키지

Pro*C 파서 확장 플러그인들을 포함합니다:
- BamCallPlugin: BAMCALL 구문 파싱
- NamingConventionPlugin: 네이밍 컨벤션 변환
- DocstringEnricherPlugin: 함수 docstring 추출

SQL 관계 플러그인은 sql_extractor.plugins로 이동되었습니다.
"""

from .naming_convention import NamingConventionPlugin, SnakeToCamelPlugin
from .bam_call import BamCallPlugin
from .docstring_enricher import DocstringEnricherPlugin

__all__ = [
    # 네이밍 컨벤션
    "NamingConventionPlugin",
    "SnakeToCamelPlugin",
    
    # 파서 플러그인
    "BamCallPlugin",
    
    # 요소 보강 플러그인
    "DocstringEnricherPlugin",
]
