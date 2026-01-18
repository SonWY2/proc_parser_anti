"""
Variable Lineage Tracker Module

Pro*C 코드에서 추출된 변수들이 MyBatis/Java로 변환되는 과정에서의
연결관계(Lineage)를 추적합니다.
"""

from .types import LineageNode, LineageLink, LineageGraph, NodeType, LinkType
from .tracker import VariableLineageTracker, LineageConfig
from .plugin_interface import NameTransformPlugin, TransformationResult
from .plugins import PrefixRemovalPlugin, SnakeToCamelPlugin
from .exporters import Neo4jExporter, LineageNeo4jPlugin

__all__ = [
    # Types
    'LineageNode',
    'LineageLink',
    'LineageGraph',
    'NodeType',
    'LinkType',
    # Core
    'VariableLineageTracker',
    'LineageConfig',
    # Plugin Interface
    'NameTransformPlugin',
    'TransformationResult',
    # Default Plugins
    'PrefixRemovalPlugin',
    'SnakeToCamelPlugin',
    # Exporters
    'Neo4jExporter',
    'LineageNeo4jPlugin',
]


