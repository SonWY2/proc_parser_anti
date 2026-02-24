"""
타입 변환 유틸리티

이름 변환 및 타입 관련 유틸리티 함수들을 제공합니다.
"""


def to_pascal_case(name: str) -> str:
    """snake_case를 PascalCase로 변환"""
    if not name:
        return ""
    components = name.replace('-', '_').split('_')
    return ''.join(x.title() for x in components)


def snake_to_camel(name: str) -> str:
    """snake_case를 camelCase로 변환"""
    if not name:
        return ""
    components = name.split('_')
    return components[0].lower() + ''.join(x.title() for x in components[1:])
