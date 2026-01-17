"""
트랜잭션 관계 플러그인

트랜잭션 경계를 감지하고 그룹화합니다:
SQL 문 -> COMMIT/ROLLBACK
"""

import re
from typing import List, Dict, Optional
from .base import SQLRelationshipPlugin


class TransactionRelationshipPlugin(SQLRelationshipPlugin):
    """
    Pro*C 코드에서 트랜잭션 관계를 감지하는 플러그인입니다.
    
    SQL 문을 트랜잭션 경계(COMMIT/ROLLBACK)로 그룹화합니다.
    Spring @Transactional 어노테이션으로 변환하는 데 유용합니다.
    """
    
    def can_handle(self, sql_elements: List[Dict]) -> bool:
        """COMMIT 또는 ROLLBACK 문이 존재하는지 확인합니다."""
        return any(el.get('sql_type', '').upper() in ['COMMIT', 'ROLLBACK'] 
                  for el in sql_elements)
    
    def extract_relationships(self, sql_elements: List[Dict], all_elements: List[Dict] = None) -> List[Dict]:
        """
        트랜잭션 관계를 추출합니다.
        
        트랜잭션 경계 사이의 SQL 문을 그룹화합니다.
        """
        relationships = []
        txn_counter = 0
        
        # 먼저 함수별로 그룹화
        functions = {}
        for el in sql_elements:
            func_name = el.get('function', 'global')
            if func_name not in functions:
                functions[func_name] = []
            functions[func_name].append(el)
        
        # 각 함수 처리
        for func_name, elements in functions.items():
            # 라인 번호로 정렬
            elements.sort(key=lambda x: x.get('line_start', 0))
            
            # 트랜잭션 경계 찾기
            boundaries = [el for el in elements 
                         if el.get('sql_type', '').upper() in ['COMMIT', 'ROLLBACK']]
            
            if not boundaries:
                continue
            
            # 각 경계 이전의 문 그룹화
            for boundary_el in boundaries:
                txn_counter += 1
                
                # 동일한 함수 내에서 이 경계 이전의 모든 SQL 문 찾기
                txn_statements = []
                for el in elements:
                    if (el.get('line_start', 0) < boundary_el.get('line_start', 0) and
                        el.get('sql_type', '').upper() not in ['COMMIT', 'ROLLBACK', 'CONNECT']):
                        # 이미 다른 트랜잭션에 포함되지 않았는지 확인
                        already_grouped = any(
                            el['sql_id'] in r['sql_ids'] 
                            for r in relationships
                        )
                        if not already_grouped:
                            txn_statements.append(el)
                
                # 트랜잭션에 문이 있는 경우에만 관계 생성
                if txn_statements:
                    related_sql_ids = [el['sql_id'] for el in txn_statements]
                    related_sql_ids.append(boundary_el['sql_id'])
                    
                    relationship_id = self._generate_relationship_id(
                        "txn", func_name or "unknown", txn_counter
                    )
                    
                    # 트랜잭션 유형 결정
                    is_commit = boundary_el.get('sql_type', '').upper() == 'COMMIT'
                    has_rollback = any(
                        el.get('sql_type', '').upper() == 'ROLLBACK' 
                        for el in elements
                        if el.get('line_start', 0) > boundary_el.get('line_start', 0)
                    )
                    
                    # 메타데이터 생성
                    metadata = {
                        'transaction_scope': 'function' if func_name != 'global' else 'global',
                        'commit_type': 'explicit',
                        'is_commit': is_commit,
                        'has_rollback': has_rollback,
                        'statement_count': len(txn_statements)
                    }
                    
                    relationships.append({
                        'relationship_id': relationship_id,
                        'relationship_type': 'TRANSACTION',
                        'sql_ids': related_sql_ids,
                        'metadata': metadata
                    })
        
        return relationships
