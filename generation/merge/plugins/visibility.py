"""
Public → Private 변환 플러그인

main 함수를 제외한 모든 public 메소드를 private로 변환.
"""

import re
from typing import List, TYPE_CHECKING

from . import register_plugin
from .base import MergePlugin, PluginPhase, PluginTarget

if TYPE_CHECKING:
    from ..types import ExtractedMethod


@register_plugin
class VisibilityPlugin(MergePlugin):
    """Public → Private 변환 플러그인.
    
    main 함수를 제외한 모든 public 메소드를 private로 변환.
    """
    
    name = "visibility"
    priority = 30  # main_deduplicator 후, bxmcategory 전에 실행
    description = "public → private 변환 (main 제외)"
    phase = PluginPhase.PRE_MERGE
    target = PluginTarget.METHOD
    
    # main 함수 식별 패턴
    MAIN_PATTERN = re.compile(r'(Main|_main)', re.IGNORECASE)
    
    # public 키워드 패턴 (메소드 시그니처에서)
    PUBLIC_PATTERN = re.compile(
        r'^(\s*)(public\s+)((?:static\s+|final\s+|synchronized\s+)*)'
        r'(void|[a-zA-Z_][a-zA-Z0-9_<>\[\], ]*)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
        re.MULTILINE
    )
    
    def is_main_method(self, method_name: str) -> bool:
        """메소드가 main 함수인지 확인."""
        return bool(self.MAIN_PATTERN.search(method_name))
    
    def process(self, method: 'ExtractedMethod') -> 'ExtractedMethod':
        """public 메소드를 private로 변환.
        
        main 함수는 변환하지 않음.
        
        Args:
            method: 추출된 메소드
            
        Returns:
            private로 변환된 메소드 (main 제외)
        """
        # main 함수는 스킵
        if self.is_main_method(method.name):
            return method
        
        body = method.body
        
        # public → private 변환
        match = self.PUBLIC_PATTERN.search(body)
        if not match:
            return method
        
        # public을 private로 교체
        new_body = self.PUBLIC_PATTERN.sub(
            r'\1private \3\4 \5(',
            body,
            count=1  # 첫 번째(시그니처)만 변환
        )
        
        # 시그니처도 업데이트
        new_signature = method.signature.replace('public ', 'private ', 1)
        
        from ..types import ExtractedMethod as EM
        return EM(
            name=method.name,
            signature=new_signature,
            body=new_body,
            start_line=method.start_line,
            end_line=method.end_line
        )
