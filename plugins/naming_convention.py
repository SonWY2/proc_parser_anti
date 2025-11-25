from abc import ABC, abstractmethod
import re

class NamingConventionPlugin(ABC):
    """
    네이밍 컨벤션 플러그인을 위한 추상 기본 클래스입니다.
    호스트 변수 이름을 대상 형식(예: snake_case에서 camelCase)으로 변환하는 데 사용됩니다.
    """
    
    @abstractmethod
    def convert(self, name: str) -> str:
        """
        변수 이름을 대상 컨벤션으로 변환합니다.
        
        Args:
            name: 원래 변수 이름 (예: "my_var").
            
        Returns:
            변환된 이름 (예: "myVar").
        """
        pass

class SnakeToCamelPlugin(NamingConventionPlugin):
    """
    snake_case를 camelCase로 변환합니다.
    예: user_id -> userId, my_long_var -> myLongVar
    """
    
    def convert(self, name: str) -> str:
        # 선행 콜론이 있으면 제거 (대개 없이 전달되지만 안전을 위해)
        clean_name = name.lstrip(':')
        
        components = clean_name.split('_')
        if not components:
            return name
            
        # 첫 번째 요소를 제외한 각 요소의 첫 글자를 대문자로 변환하고
        # 'title' 메서드를 사용하여 결합합니다.
        return components[0] + ''.join(x.title() for x in components[1:])
