"""
@bxmcategory 어노테이션 자동 추가 플러그인

메소드 시그니처 위에 @bxmcategory 어노테이션이 없으면 자동 추가.
"""

import re
from typing import TYPE_CHECKING

from . import register_plugin
from .base import MergePlugin, PluginPhase, PluginTarget

if TYPE_CHECKING:
    from ..types import ExtractedMethod


@register_plugin
class BxmCategoryPlugin(MergePlugin):
    """@bxmcategory 어노테이션 자동 추가 플러그인.
    
    모든 메소드 시그니처 위에 @bxmcategory 어노테이션이 없으면 추가.
    """
    
    name = "bxmcategory"
    priority = 50  # 다른 변환 후에 실행
    description = "@bxmcategory 어노테이션 자동 추가"
    phase = PluginPhase.PRE_MERGE
    target = PluginTarget.METHOD
    
    # 어노테이션 이름
    ANNOTATION = "@bxmcategory"
    
    # 메소드 시그니처 시작 패턴 (접근제한자 또는 반환타입으로 시작)
    METHOD_START_PATTERN = re.compile(
        r'^(\s*)((?:public|private|protected|static|final|synchronized|native|abstract|strictfp|\s)*)'
        r'\s*(void|[a-zA-Z_][a-zA-Z0-9_<>\[\], ]*)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
        re.MULTILINE
    )
    
    def process(self, method: 'ExtractedMethod') -> 'ExtractedMethod':
        """메소드에 @bxmcategory 어노테이션 추가.
        
        Args:
            method: 추출된 메소드
            
        Returns:
            어노테이션이 추가된 메소드
        """
        body = method.body
        
        # 이미 @bxmcategory가 있으면 스킵
        if self.ANNOTATION in body:
            return method
        
        # 메소드 시그니처 찾기
        match = self.METHOD_START_PATTERN.search(body)
        if not match:
            return method
        
        # 시그니처 앞에 어노테이션 삽입
        indent = match.group(1)  # 기존 들여쓰기 유지
        insert_pos = match.start()
        
        new_body = (
            body[:insert_pos] + 
            f"{indent}{self.ANNOTATION}\n" + 
            body[insert_pos:]
        )
        
        # ExtractedMethod는 frozen이 아니므로 새 인스턴스 생성
        from ..types import ExtractedMethod as EM
        return EM(
            name=method.name,
            signature=method.signature,
            body=new_body,
            start_line=method.start_line,
            end_line=method.end_line
        )
