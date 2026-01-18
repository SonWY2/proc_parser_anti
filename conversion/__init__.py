"""
Pro*C to Java 변환 모듈

LLM을 활용하여 Pro*C/SQC 파일을 Java(Spring+MyBatis)로 변환합니다.

사용 예:
    from conversion import ProcToJavaConverter, PromptBuilder
    
    converter = ProcToJavaConverter(llm_client, config)
    result = converter.convert(metadata)
"""

from .types import (
    ConversionConfig,
    SkeletonResult,
    FunctionConversionResult,
    ConversionResult,
)
from .prompt_builder import PromptBuilder
from .core import ProcToJavaConverter
from .plugin_interface import ConversionPlugin
from .prompt_exporter import PromptExporter

__all__ = [
    "ProcToJavaConverter",
    "PromptBuilder",
    "PromptExporter",
    "ConversionPlugin",
    "ConversionConfig",
    "SkeletonResult",
    "FunctionConversionResult",
    "ConversionResult",
]
