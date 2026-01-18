"""
헤더 파서 플러그인 패키지

기본 제공 플러그인들을 노출합니다.
"""
from .macro_parser_plugin import MacroParserPlugin
from .typedef_parser_plugin import TypedefParserPlugin
from .stp_parser_plugin import STPParserPlugin

__all__ = [
    "MacroParserPlugin",
    "TypedefParserPlugin",
    "STPParserPlugin",
]


def get_default_plugins():
    """기본 플러그인 인스턴스 목록 반환"""
    return [
        MacroParserPlugin(),
        TypedefParserPlugin(),
        STPParserPlugin(),
    ]
