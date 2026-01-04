"""
translation_merge 모듈

Pro*C → Java 변환 결과물(클래스 스켈레톤 + 개별 메소드)을 
하나의 완전한 Java 클래스로 병합하는 기능 제공.

Example:
    from translation_merge import TranslationMerger, MethodTranslation
    
    merger = TranslationMerger()
    
    result = merger.merge(
        class_skeleton='''
package com.example;

import java.util.List;

public class MyProgram {
}
''',
        method_translations=[
            MethodTranslation(
                name="processData",
                llm_response='''
import java.util.ArrayList;

public void processData() {
    List<String> data = new ArrayList<>();
    // ... 로직
}
'''
            ),
        ]
    )
    
    print(result.merged_code)
"""

from .types import MethodTranslation, ExtractedMethod, MergeResult
from .java_parser import JavaParser
from .merger import TranslationMerger
from .plugins import (
    MergePlugin,
    PluginPhase,
    PluginTarget,
    register_plugin,
    load_plugins,
    load_plugins_by_phase,
    list_plugins,
)


__all__ = [
    # 메인 클래스
    "TranslationMerger",
    
    # 파서
    "JavaParser",
    
    # 데이터 타입
    "MethodTranslation",
    "ExtractedMethod",
    "MergeResult",
    
    # 플러그인 시스템
    "MergePlugin",
    "PluginPhase",
    "PluginTarget",
    "register_plugin",
    "load_plugins",
    "load_plugins_by_phase",
    "list_plugins",
]

