"""
SQL Transform Plugin 기본 클래스

플러그인 인터페이스와 파이프라인 실행기를 정의합니다.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class TransformResult:
    """변환 결과"""
    sql: str
    transformed: bool
    plugin_name: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class SQLTransformPlugin(ABC):
    """
    SQL 변환 플러그인 기본 클래스
    
    모든 변환 플러그인은 이 클래스를 상속받아야 합니다.
    
    Attributes:
        name: 플러그인 이름
        priority: 실행 순서 (낮을수록 먼저 실행)
        enabled: 활성화 여부
    
    Example:
        class MyPlugin(SQLTransformPlugin):
            name = "my_plugin"
            priority = 50
            
            def can_transform(self, sql, sql_type, metadata):
                return sql_type == "select"
            
            def transform(self, sql, sql_type, metadata):
                return sql.replace("OLD", "NEW")
    """
    
    name: str = "base_plugin"
    priority: int = 100  # 기본 우선순위
    enabled: bool = True
    
    @abstractmethod
    def can_transform(
        self, 
        sql: str, 
        sql_type: str, 
        metadata: Dict[str, Any]
    ) -> bool:
        """
        이 플러그인이 SQL을 변환할 수 있는지 확인
        
        Args:
            sql: SQL 문자열
            sql_type: SQL 타입 (select, insert, update, delete 등)
            metadata: 추가 메타데이터 (is_cursor_based, db_type 등)
        
        Returns:
            변환 가능하면 True
        """
        pass
    
    @abstractmethod
    def transform(
        self, 
        sql: str, 
        sql_type: str, 
        metadata: Dict[str, Any]
    ) -> str:
        """
        SQL 변환 실행
        
        Args:
            sql: 원본 SQL
            sql_type: SQL 타입
            metadata: 추가 메타데이터
        
        Returns:
            변환된 SQL
        """
        pass
    
    def get_info(self) -> Dict[str, Any]:
        """플러그인 정보 반환"""
        return {
            "name": self.name,
            "priority": self.priority,
            "enabled": self.enabled,
        }


class TransformPipeline:
    """
    플러그인 파이프라인
    
    등록된 플러그인들을 순차적으로 실행합니다.
    우선순위(priority)가 낮은 플러그인이 먼저 실행됩니다.
    
    Example:
        pipeline = TransformPipeline()
        pipeline.register(MySQLPaginationPlugin())
        pipeline.register(OracleToMySQLPlugin())
        
        result = pipeline.transform(
            sql="SELECT * FROM users",
            sql_type="select",
            metadata={"is_cursor_based": True}
        )
    """
    
    def __init__(self):
        self._plugins: List[SQLTransformPlugin] = []
        self._sorted = True
    
    def register(self, plugin: SQLTransformPlugin) -> 'TransformPipeline':
        """
        플러그인 등록
        
        Args:
            plugin: SQLTransformPlugin 인스턴스
        
        Returns:
            self (체이닝 가능)
        """
        self._plugins.append(plugin)
        self._sorted = False
        return self
    
    def unregister(self, plugin_name: str) -> bool:
        """
        플러그인 등록 해제
        
        Args:
            plugin_name: 플러그인 이름
        
        Returns:
            성공 여부
        """
        for i, plugin in enumerate(self._plugins):
            if plugin.name == plugin_name:
                self._plugins.pop(i)
                return True
        return False
    
    def enable(self, plugin_name: str, enabled: bool = True):
        """플러그인 활성화/비활성화"""
        for plugin in self._plugins:
            if plugin.name == plugin_name:
                plugin.enabled = enabled
                break
    
    def transform(
        self,
        sql: str,
        sql_type: str,
        metadata: Dict[str, Any] = None
    ) -> TransformResult:
        """
        등록된 모든 플러그인으로 SQL 변환
        
        Args:
            sql: 원본 SQL
            sql_type: SQL 타입
            metadata: 추가 메타데이터
        
        Returns:
            TransformResult 객체
        """
        metadata = metadata or {}
        
        # 우선순위 정렬
        if not self._sorted:
            self._plugins.sort(key=lambda p: p.priority)
            self._sorted = True
        
        current_sql = sql
        transformed = False
        applied_plugins = []
        
        for plugin in self._plugins:
            if not plugin.enabled:
                continue
            
            try:
                if plugin.can_transform(current_sql, sql_type, metadata):
                    new_sql = plugin.transform(current_sql, sql_type, metadata)
                    if new_sql != current_sql:
                        current_sql = new_sql
                        transformed = True
                        applied_plugins.append(plugin.name)
            except Exception as e:
                # 플러그인 에러는 무시하고 계속 진행
                metadata.setdefault('errors', []).append({
                    'plugin': plugin.name,
                    'error': str(e)
                })
        
        return TransformResult(
            sql=current_sql,
            transformed=transformed,
            plugin_name=','.join(applied_plugins),
            metadata={'applied_plugins': applied_plugins}
        )
    
    def get_plugins(self) -> List[Dict[str, Any]]:
        """등록된 플러그인 목록 반환"""
        return [p.get_info() for p in self._plugins]
    
    def clear(self):
        """모든 플러그인 제거"""
        self._plugins.clear()
        self._sorted = True


# 전역 파이프라인 (편의용)
_global_pipeline: Optional[TransformPipeline] = None


def get_global_pipeline() -> TransformPipeline:
    """전역 파이프라인 반환"""
    global _global_pipeline
    if _global_pipeline is None:
        _global_pipeline = TransformPipeline()
    return _global_pipeline


def reset_global_pipeline():
    """전역 파이프라인 리셋"""
    global _global_pipeline
    if _global_pipeline:
        _global_pipeline.clear()
