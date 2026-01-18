"""
Prefix Removal Plugin

변수명에서 특정 prefix(H_o_, H_i_, H_, W_ 등)를 제거하는 플러그인입니다.
"""

from typing import List, Optional

from ..plugin_interface import NameTransformPlugin, TransformationResult


class PrefixRemovalPlugin(NameTransformPlugin):
    """
    Prefix 제거 플러그인
    
    Pro*C 호스트 변수 네이밍 컨벤션에서 사용되는 prefix를 제거합니다.
    
    기본 prefix 목록:
    - H_o_: Host Output 변수
    - H_i_: Host Input 변수
    - H_: Host 변수
    - W_: Work 변수
    
    Example:
        plugin = PrefixRemovalPlugin()
        result = plugin.transform("H_o_user_id")
        # result.name = "user_id"
        # result.transformations = ["prefix_removed:H_o_"]
        
        # 커스텀 prefix 사용
        plugin = PrefixRemovalPlugin(prefixes=['CUSTOM_', 'MY_'])
        result = plugin.transform("CUSTOM_field")
        # result.name = "field"
    """
    
    DEFAULT_PREFIXES = ['H_o_', 'H_i_', 'H_', 'W_']
    
    def __init__(self, prefixes: Optional[List[str]] = None):
        """
        Args:
            prefixes: 제거할 prefix 목록. None이면 기본값 사용.
                      긴 prefix가 먼저 매칭되도록 자동 정렬됩니다.
        """
        self._prefixes = prefixes if prefixes is not None else self.DEFAULT_PREFIXES.copy()
        # 긴 prefix 먼저 매칭되도록 정렬
        self._prefixes.sort(key=len, reverse=True)
    
    def name(self) -> str:
        return "prefix_removal"
    
    def description(self) -> str:
        return f"Removes prefixes from variable names: {self._prefixes}"
    
    @property
    def prefixes(self) -> List[str]:
        """현재 설정된 prefix 목록 반환"""
        return self._prefixes.copy()
    
    def transform(self, name: str) -> TransformationResult:
        """
        이름에서 prefix 제거
        
        첫 번째로 매칭되는 prefix만 제거됩니다.
        
        Args:
            name: 변환할 이름
            
        Returns:
            TransformationResult: prefix가 제거된 이름 및 변환 규칙
        """
        for prefix in self._prefixes:
            if name.startswith(prefix):
                return TransformationResult(
                    name=name[len(prefix):],
                    transformations=[f"prefix_removed:{prefix}"]
                )
        
        # 매칭되는 prefix 없음
        return TransformationResult(name=name, transformations=[])
