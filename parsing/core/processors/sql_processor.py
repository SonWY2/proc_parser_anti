"""
SQL 프로세서

SQL 처리를 담당합니다: MyBatis 변환, 중복 감지, 관계 수집
"""
import re
from typing import Dict, List, Any
from collections import defaultdict

try:
    from ..processor_interface import MetadataProcessor
except ImportError:
    from parsing.core.processor_interface import MetadataProcessor


class SQLProcessor(MetadataProcessor):
    """
    SQL 요소 처리를 담당하는 프로세서
    
    기능:
    - MyBatis 형식 SQL 추가
    - SQL 중복 감지
    - SQL 관계 수집
    """
    
    # MyBatis 변환에서 제외할 SQL 타입
    IGNORE_TYPES = {'BEGIN', 'END', 'INCLUDE', 'VAR', 'TYPE', 'WHENEVER'}
    
    def __init__(self):
        pass
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        SQL 처리 수행
        
        Args:
            context:
                - sql_elements: SQL 요소 목록
                
        Returns:
            - sql_elements: 보강된 SQL 목록 (mybatis_sql, duplicate 정보 추가)
            - sql_relationships: 관계 목록
        """
        sql_elements = context.get('sql_elements', [])
        
        # 1. MyBatis 형식 추가
        self._add_mybatis_sql(sql_elements)
        
        # 2. 중복 감지
        self._detect_sql_duplicates(sql_elements)
        
        # 3. 관계 수집
        sql_relationships = self._collect_sql_relationships(sql_elements)
        
        return {
            "sql_elements": sql_elements,
            "sql_relationships": sql_relationships
        }
    
    def _add_mybatis_sql(self, sql_elements: List[Dict]):
        """SQL에 MyBatis 형식 추가"""
        for sql in sql_elements:
            # 1. 불필요한 SQL 필터링 (MyBatis 변환 제외)
            sql_type = sql.get('sql_type', '').upper()
            raw_content = sql.get('raw_content', '').upper()
            
            if sql_type in self.IGNORE_TYPES or 'DECLARE SECTION' in raw_content:
                 sql['mybatis_sql'] = None
                 continue

            normalized = sql.get('normalized_sql', '')
            if normalized:
                # :host_var → #{hostVar, jdbcType=VARCHAR}
                def replace_host_var(match):
                    var_name = match.group(1)
                    camel_name = self._snake_to_camel(var_name)
                    jdbc_type = "VARCHAR"  # 기본값
                    return "#{" + camel_name + ", jdbcType=" + jdbc_type + "}"
                
                mybatis_sql = re.sub(r':(\w+)', replace_host_var, normalized)
                sql['mybatis_sql'] = mybatis_sql
    
    def _detect_sql_duplicates(self, sql_elements: List[Dict]):
        """
        SQL 중복 감지 - normalized_sql 완전 일치 기준
        
        각 SQL에 다음 필드 추가:
        - is_duplicate: 중복 여부
        - duplicate_group_id: 중복 그룹 ID (dup_001, dup_002, ...)
        - call_sites: 동일 SQL의 모든 호출 위치 목록
        """
        # 1. normalized_sql 기준으로 그룹화
        sql_groups: Dict[str, List[Dict]] = defaultdict(list)
        
        for sql in sql_elements:
            normalized = sql.get('normalized_sql', '')
            if normalized:
                sql_groups[normalized].append(sql)
        
        # 2. 중복 그룹에 ID 할당 및 필드 추가
        dup_group_counter = 0
        
        for normalized_sql, group in sql_groups.items():
            is_duplicate = len(group) > 1
            
            if is_duplicate:
                dup_group_counter += 1
                group_id = f"dup_{dup_group_counter:03d}"
                
                # 모든 호출 위치 수집
                call_sites = []
                for sql in group:
                    call_sites.append({
                        "sql_id": sql.get('sql_id'),
                        "function": sql.get('function'),
                        "line_start": sql.get('line_start'),
                        "line_end": sql.get('line_end')
                    })
                
                # 각 SQL에 중복 정보 추가
                for sql in group:
                    sql['is_duplicate'] = True
                    sql['duplicate_group_id'] = group_id
                    sql['duplicate_count'] = len(group)
                    sql['call_sites'] = call_sites
            else:
                # 중복이 아닌 경우
                for sql in group:
                    sql['is_duplicate'] = False
                    sql['duplicate_group_id'] = None
                    sql['duplicate_count'] = 1
                    sql['call_sites'] = [{
                        "sql_id": sql.get('sql_id'),
                        "function": sql.get('function'),
                        "line_start": sql.get('line_start'),
                        "line_end": sql.get('line_end')
                    }]
    
    def _collect_sql_relationships(self, sql_elements: List[Dict]) -> List[Dict]:
        """
        SQL 요소에서 관계 정보를 수집 (중복 제거)
        ProCParser가 이미 relationship 필드를 채웠다고 가정
        """
        relationships = {}
        
        for sql in sql_elements:
            rel = sql.get('relationship')
            if rel:
                rel_id = rel.get('relationship_id')
                if rel_id and rel_id not in relationships:
                    # 원본 관계 메타데이터 복원
                    relationships[rel_id] = {
                        "relationship_id": rel_id,
                        "relationship_type": rel.get('relationship_type'),
                        "metadata": rel.get('metadata'),
                    }
        
        # SQL ID 목록 재구성
        for rel_id in relationships:
            relationships[rel_id]['sql_ids'] = []
            
        for sql in sql_elements:
            rel = sql.get('relationship')
            if rel:
                rel_id = rel.get('relationship_id')
                if rel_id in relationships:
                    relationships[rel_id]['sql_ids'].append(sql.get('sql_id'))
        
        # Dictionary -> List 변환
        return list(relationships.values())
    
    def _snake_to_camel(self, name: str) -> str:
        """snake_case를 camelCase로 변환"""
        components = name.split('_')
        return components[0].lower() + ''.join(x.title() for x in components[1:])
