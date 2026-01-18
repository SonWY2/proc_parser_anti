"""
Function Context 모듈

특정 함수에 대한 모든 관련 정보(SQL, 변수, 매크로, 구조체, 아티팩트)를 추출합니다.

사용 예시:
    >>> from function_context import FunctionContextExtractor
    >>> extractor = FunctionContextExtractor(metadata)
    >>> ctx = extractor.extract("process_data", include_sql=True, include_mybatis=True)
    >>> print(ctx.sql)
    >>> print(ctx.mybatis_xml)
"""

from .types import FunctionContext, FunctionInfo
from .indexer import MetadataIndexer
from .artifact_generator import FunctionArtifactGenerator
from .extractor import FunctionContextExtractor

__all__ = [
    "FunctionContextExtractor",
    "FunctionContext",
    "FunctionInfo",
    "MetadataIndexer",
    "FunctionArtifactGenerator",
]
