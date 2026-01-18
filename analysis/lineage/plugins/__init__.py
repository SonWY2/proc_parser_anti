"""
Lineage Name Transform Plugins

이름 변환 플러그인 모음입니다.
"""

from .prefix_removal import PrefixRemovalPlugin
from .snake_to_camel import SnakeToCamelPlugin

__all__ = [
    'PrefixRemovalPlugin',
    'SnakeToCamelPlugin',
]
