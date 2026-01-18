"""
Snake to Camel Case Plugin

snake_case 변수명을 camelCase로 변환하는 플러그인입니다.
"""

from ..plugin_interface import NameTransformPlugin, TransformationResult


class SnakeToCamelPlugin(NameTransformPlugin):
    """
    snake_case → camelCase 변환 플러그인
    
    Pro*C/C 스타일의 snake_case 변수명을 Java 스타일의 camelCase로 변환합니다.
    
    Example:
        plugin = SnakeToCamelPlugin()
        result = plugin.transform("user_id")
        # result.name = "userId"
        # result.transformations = ["snake_to_camel"]
        
        result = plugin.transform("already_camel")
        # result.name = "alreadyCamel"
        
        result = plugin.transform("nochange")
        # result.name = "nochange"
        # result.transformations = []  # underscore가 없으면 변환 없음
    """
    
    def name(self) -> str:
        return "snake_to_camel"
    
    def description(self) -> str:
        return "Converts snake_case names to camelCase"
    
    def transform(self, name: str) -> TransformationResult:
        """
        snake_case를 camelCase로 변환
        
        Args:
            name: 변환할 이름 (snake_case 형식)
            
        Returns:
            TransformationResult: camelCase로 변환된 이름 및 변환 규칙
        """
        if '_' not in name:
            # underscore가 없으면 변환할 필요 없음
            return TransformationResult(name=name, transformations=[])
        
        parts = name.split('_')
        if not parts:
            return TransformationResult(name=name, transformations=[])
        
        # 첫 부분은 소문자, 나머지는 Title Case
        camel_name = parts[0].lower() + ''.join(x.title() for x in parts[1:])
        
        return TransformationResult(
            name=camel_name,
            transformations=["snake_to_camel"]
        )
