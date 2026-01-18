"""
Neo4j Client

Neo4j 데이터베이스 연결 및 쿼리 실행을 담당하는 범용 클라이언트입니다.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any


def load_db_env(env_file: str = None) -> Dict[str, str]:
    """
    .db.env 파일에서 Neo4j 연결 정보 로드
    
    Args:
        env_file: .db.env 파일 경로 (기본: 프로젝트 루트)
        
    Returns:
        환경 변수 딕셔너리
    """
    if env_file is None:
        # 프로젝트 루트에서 .db.env 찾기
        current = Path(__file__).parent
        for _ in range(5):  # 최대 5단계 상위까지 검색
            env_path = current / '.db.env'
            if env_path.exists():
                env_file = str(env_path)
                break
            current = current.parent
    
    config = {}
    if env_file and os.path.exists(env_file):
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
    
    return config


class Neo4jClient:
    """
    Neo4j 데이터베이스 클라이언트
    
    Usage:
        # 1. 직접 연결
        client = Neo4jClient()
        client.connect("bolt://localhost:7687", "neo4j", "password")
        
        # 2. 환경 파일에서 자동 연결
        client = Neo4jClient.from_env()
        
        # 3. 쿼리 실행
        client.run("CREATE (n:Test {name: $name})", name="test")
        results = client.run("MATCH (n) RETURN n")
    """
    
    def __init__(self):
        self.driver = None
        self.database = "neo4j"
    
    @classmethod
    def from_env(cls, env_file: str = None) -> 'Neo4jClient':
        """
        .db.env 파일에서 설정을 로드하여 인스턴스 생성 및 연결
        
        Args:
            env_file: .db.env 파일 경로
            
        Returns:
            연결된 Neo4jClient 인스턴스
        """
        config = load_db_env(env_file)
        client = cls()
        
        if config.get('NEO4J_URI'):
            client.connect(
                uri=config.get('NEO4J_URI', 'bolt://localhost:7687'),
                user=config.get('NEO4J_USER', 'neo4j'),
                password=config.get('NEO4J_PASSWORD', ''),
                database=config.get('NEO4J_DATABASE', 'neo4j')
            )
        
        return client
    
    def connect(self, uri: str, user: str, password: str, database: str = "neo4j") -> bool:
        """
        Neo4j 데이터베이스에 연결
        
        Args:
            uri: Neo4j Bolt URI (e.g., bolt://localhost:7687)
            user: 사용자명
            password: 비밀번호
            database: 데이터베이스명
            
        Returns:
            연결 성공 여부
        """
        try:
            from neo4j import GraphDatabase
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            self.database = database
            # 연결 테스트
            with self.driver.session(database=database) as session:
                session.run("RETURN 1")
            return True
        except ImportError:
            print("Warning: neo4j 패키지가 설치되지 않았습니다. pip install neo4j")
            return False
        except Exception as e:
            print(f"Neo4j 연결 실패: {e}")
            return False
    
    def is_connected(self) -> bool:
        """연결 상태 확인"""
        return self.driver is not None
    
    def close(self):
        """연결 종료"""
        if self.driver:
            self.driver.close()
            self.driver = None
    
    def run(self, query: str, **params) -> List[Dict[str, Any]]:
        """
        Cypher 쿼리 실행
        
        Args:
            query: Cypher 쿼리문
            **params: 쿼리 파라미터
            
        Returns:
            결과 레코드 리스트
        """
        if not self.is_connected():
            raise RuntimeError("Neo4j에 연결되지 않았습니다.")
        
        with self.driver.session(database=self.database) as session:
            result = session.run(query, **params)
            return [dict(record) for record in result]
    
    def run_many(self, queries: List[str]) -> int:
        """
        여러 Cypher 쿼리 순차 실행
        
        Args:
            queries: Cypher 쿼리문 리스트
            
        Returns:
            성공한 쿼리 수
        """
        if not self.is_connected():
            raise RuntimeError("Neo4j에 연결되지 않았습니다.")
        
        success_count = 0
        with self.driver.session(database=self.database) as session:
            for query in queries:
                try:
                    session.run(query)
                    success_count += 1
                except Exception as e:
                    print(f"쿼리 실행 실패: {e}")
        
        return success_count
    
    def create_index(self, label: str, property_name: str) -> bool:
        """
        노드 인덱스 생성
        
        Args:
            label: 노드 라벨
            property_name: 속성명
            
        Returns:
            생성 성공 여부
        """
        try:
            self.run(
                f"CREATE INDEX idx_{label.lower()}_{property_name} "
                f"IF NOT EXISTS FOR (n:{label}) ON (n.{property_name})"
            )
            return True
        except Exception as e:
            if "already exists" not in str(e).lower():
                print(f"인덱스 생성 실패: {e}")
            return False
    
    def create_constraint(self, label: str, property_name: str) -> bool:
        """
        유니크 제약조건 생성
        
        Args:
            label: 노드 라벨
            property_name: 속성명
            
        Returns:
            생성 성공 여부
        """
        try:
            self.run(
                f"CREATE CONSTRAINT uniq_{label.lower()}_{property_name} "
                f"IF NOT EXISTS FOR (n:{label}) REQUIRE n.{property_name} IS UNIQUE"
            )
            return True
        except Exception as e:
            if "already exists" not in str(e).lower():
                print(f"제약조건 생성 실패: {e}")
            return False
