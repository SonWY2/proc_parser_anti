"""
Array DML 관계 플러그인

Array DML 작업(FOR 절)을 감지하고 그룹화합니다:
FOR :array_size INSERT/UPDATE/DELETE ...
"""

import re
from typing import List, Dict, Optional
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sql_relationship_plugin import SQLRelationshipPlugin


class ArrayDMLRelationshipPlugin(SQLRelationshipPlugin):
    """
    Pro*C 코드에서 Array DML(대량 작업)을 감지하는 플러그인입니다.
    
    Array DML은 FOR 절을 사용하여 배열에 대해 DML을 실행합니다:
    EXEC SQL FOR :array_size
      INSERT INTO table VALUES (:arr1[i], :arr2[i]);
    
    이 플러그인은 MyBatis <foreach> 태그로 변환하기 위한 메타데이터를 추출합니다.
    """
    
    def can_handle(self, sql_elements: List[Dict]) -> bool:
        """Array DML 패턴이 존재하는지 확인합니다."""
        return any(self._is_array_dml(el) for el in sql_elements)
    
    def extract_relationships(self, sql_elements: List[Dict]) -> List[Dict]:
        """
        Array DML 관계를 추출합니다.
        
        Array DML 메타데이터가 포함된 관계 딕셔너리 목록을 반환합니다.
        """
        relationships = []
        array_counter = 0
        
        for el in sql_elements:
            if not self._is_array_dml(el):
                continue
            
            array_counter += 1
            
            # 관계 ID 생성
            func_name = el.get('function', 'unknown')
            relationship_id = self._generate_relationship_id(
                "array", func_name, array_counter
            )
            
            # 배열 크기 변수 추출
            array_size_var = self._extract_array_size_var(el)
            
            # 배열 호스트 변수 추출 ([i] 또는 배열 첨자가 있는 변수)
            array_host_vars = self._extract_array_variables(el)
            
            # DML 유형 결정
            dml_type = el.get('sql_type', 'UNKNOWN').upper()
            if dml_type not in ['INSERT', 'UPDATE', 'DELETE']:
                # 원시 콘텐츠에서 추출 시도
                raw = el.get('raw_content', '').upper()
                for dtype in ['INSERT', 'UPDATE', 'DELETE']:
                    if dtype in raw:
                        dml_type = dtype
                        break
            
            # 메타데이터 생성
            metadata = {
                'array_size_var': array_size_var,
                'array_host_vars': array_host_vars,
                'dml_type': dml_type,
                'mybatis_hint': 'use_foreach'
            }
            
            relationships.append({
                'relationship_id': relationship_id,
                'relationship_type': 'ARRAY_DML',
                'sql_ids': [el['sql_id']],
                'metadata': metadata
            })
        
        return relationships
    
    def _is_array_dml(self, element: Dict) -> bool:
        """Check if element is an array DML statement."""
        raw = element.get('raw_content', '')
        normalized = element.get('normalized_sql', '').upper()
        
        # CURSOR 선언을 명시적으로 제외
        if 'CURSOR FOR' in normalized or 'CURSOR FOR' in raw.upper():
            return False
            
        # FOR 절 패턴 확인
        # FOR :variable 또는 FOR number여야 함
        # 'FOR UPDATE', 'FOR SELECT' 등과의 매칭 방지
        return bool(re.search(r'FOR\s+(:[a-zA-Z_]\w*|\d+)', raw, re.IGNORECASE))
    
    def _extract_array_size_var(self, element: Dict) -> str:
        """Extract the array size variable from FOR clause."""
        raw = element.get('raw_content', '')
        # 패턴: FOR :array_size 또는 FOR array_size
        match = re.search(r'FOR\s+(:?\w+)', raw, re.IGNORECASE)
        return match.group(1) if match else ''
    
    def _extract_array_variables(self, element: Dict) -> List[Dict]:
        """
        Extract array variables (those with subscripts like :arr[i]).
        
        Returns list of dicts with var name and is_array flag.
        """
        raw = element.get('raw_content', '')
        array_vars = []
        
        # 패턴: :varname[index] 또는 :varname
        # 먼저 첨자가 있는 모든 항목 찾기
        array_pattern = re.compile(r':(\w+)\[', re.IGNORECASE)
        for match in array_pattern.finditer(raw):
            var_name = ':' + match.group(1)
            if not any(v['var'] == var_name for v in array_vars):
                array_vars.append({
                    'var': var_name,
                    'is_array': True
                })
        
        # input_host_vars의 일반 호스트 변수도 포함
        # (일부는 정규화된 형식에서 명시적 첨자가 없을 수 있음)
        for var in element.get('input_host_vars', []):
            if not any(v['var'] == var for v in array_vars):
                # FOR 절이 존재하면 배열로 가정
                array_vars.append({
                    'var': var,
                    'is_array': True
                })
        
        return array_vars
