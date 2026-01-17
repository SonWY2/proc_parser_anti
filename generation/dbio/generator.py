"""
DBIO 파일 생성기 (MyBatis XML)
SQL 정보를 MyBatis Mapper XML로 변환합니다.
"""
import os
import html
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime
import sys

# 상위 디렉토리를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared_config import (
    SQL_TYPE_TO_MYBATIS_TAG,
    DDL_TYPES,
    DEFAULT_RESULT_TYPES,
    get_mybatis_tag,
    is_ddl,
    get_jdbc_type,
    snake_to_camel,
)


class DBIOGenerator:
    """
    DBIO (MyBatis XML) 파일 생성 클래스
    
    SQL 정보를 받아 MyBatis Mapper XML 파일을 생성합니다.
    
    출력 포맷:
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" 
            "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
        <mapper namespace="{package}.{DaoName}">
            <select id="{sqlId}" parameterType="{inputType}" resultType="{outputType}">
                {SQL}
            </select>
        </mapper>
    
    사용 예:
        generator = DBIOGenerator(base_package="com.example.dao")
        content = generator.generate(sql_calls, id_to_path_map, "SPAA0010Dao")
    """
    
    XML_HEADER = '<?xml version="1.0" encoding="UTF-8"?>'
    DOCTYPE = '<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">'
    
    def __init__(
        self,
        base_package: str,
        datasource: str = "MainDS",
        output_dir: Optional[str] = None
    ):
        """
        Args:
            base_package: Java 패키지 루트 (예: "com.example.dao")
            datasource: 데이터소스 이름
            output_dir: 출력 디렉토리 (파일 저장할 경우)
        """
        self.base_package = base_package
        self.datasource = datasource
        self.output_dir = output_dir
    
    def generate(
        self,
        sql_calls: List[Dict],
        id_to_path_map: Dict[str, str],
        dao_name: str
    ) -> str:
        """
        DBIO 파일 내용 생성
        
        Args:
            sql_calls: SQL 호출 정보 리스트
                [
                    {
                        "name": "selectAcntId",
                        "sql_type": "select",
                        "parsed_sql": "SELECT ACNT_ID ...",
                        "input_vars": ["acntNoCryp"],
                        "output_vars": ["acntId"],
                    },
                    ...
                ]
            id_to_path_map: SQL ID → DTO 경로 매핑
                {
                    "selectAcntIdIn": "com.example.dao.dto.SelectAcntIdIn",
                    "selectAcntIdOut": "com.example.dao.dto.SelectAcntIdOut",
                }
            dao_name: DAO 이름 (예: "SPAA0010Dao")
            
        Returns:
            MyBatis XML 파일 내용 문자열
        """
        namespace = f"{self.base_package}.{dao_name}"
        timestamp = datetime.now().strftime("%Y. %m. %d. %H:%M:%S")
        
        lines = []
        lines.append(self.XML_HEADER)
        lines.append(self.DOCTYPE)
        lines.append(f'<mapper namespace="{namespace}">')
        lines.append(f"<!--Generated {timestamp}-->")
        
        # SQL 태그들
        for sql_obj in sql_calls:
            sql_element = self._generate_sql_element(sql_obj, id_to_path_map)
            lines.append(sql_element)
        
        lines.append("</mapper>")
        
        return "\r\n".join(lines)
    
    def _generate_sql_element(
        self,
        sql_obj: Dict,
        id_to_path_map: Dict[str, str]
    ) -> str:
        """
        단일 SQL 태그 생성
        
        Args:
            sql_obj: SQL 정보 딕셔너리
            id_to_path_map: DTO 경로 매핑
            
        Returns:
            MyBatis SQL 태그 문자열
        """
        sql_id = sql_obj.get("name", "unnamed")
        sql_type = sql_obj.get("sql_type", "select").lower()
        parsed_sql = sql_obj.get("parsed_sql", "")
        input_vars = sql_obj.get("input_vars", [])
        output_vars = sql_obj.get("output_vars", [])
        
        # MyBatis 태그 결정
        tag = get_mybatis_tag(sql_type)
        
        # DTO 경로 조회
        param_type = id_to_path_map.get(f"{sql_id}In", "")
        result_type = id_to_path_map.get(f"{sql_id}Out", "")
        
        # DDL인 경우 타입 생략
        if is_ddl(sql_type):
            param_type = ""
            result_type = ""
        
        # 기본 반환 타입 (DTO 없는 경우)
        if not result_type and not is_ddl(sql_type):
            result_type = DEFAULT_RESULT_TYPES.get(sql_type, "java.lang.String")
        
        # SQL 처리 (호스트 변수 → MyBatis 파라미터)
        processed_sql = self._process_sql(parsed_sql)
        
        # 태그 시작
        attrs = [f'id="{sql_id}"']
        if param_type:
            attrs.append(f'parameterType="{param_type}"')
        if result_type:
            attrs.append(f'resultType="{result_type}"')
        
        attrs_str = " ".join(attrs)
        
        # XML 이스케이프 및 &amp;#13; 추가 (줄바꿈 보존)
        escaped_sql = self._escape_xml(processed_sql)
        
        return f"<{tag} {attrs_str}>&#13;\r\n{escaped_sql}&#13;\r\n</{tag}>"
    
    def _process_sql(self, sql: str) -> str:
        """
        SQL 처리: 호스트 변수를 MyBatis 파라미터로 변환
        
        :host_var → #{hostVar, jdbcType=VARCHAR}
        """
        import re
        
        def replace_host_var(match):
            var_name = match.group(1)
            camel_name = snake_to_camel(var_name)
            jdbc_type = get_jdbc_type("char")  # 기본값 VARCHAR
            return "#{" + camel_name + ", jdbcType=" + jdbc_type + "}"
        
        # :variable 패턴 매칭 (문자열 리터럴 내부 제외)
        # 간단한 구현: 모든 :word 패턴 변환
        result = re.sub(r':(\w+)', replace_host_var, sql)
        
        return result
    
    def _escape_xml(self, text: str) -> str:
        """XML 특수문자 이스케이프"""
        # html.escape()은 &, <, >, ", '를 이스케이프
        return html.escape(text, quote=False)
    
    def write(self, content: str, dao_name: str) -> str:
        """
        DBIO 내용을 파일로 저장
        
        Args:
            content: DBIO 파일 내용
            dao_name: DAO 이름
            
        Returns:
            저장된 파일 경로
        """
        if not self.output_dir:
            raise ValueError("output_dir가 설정되지 않았습니다")
        
        file_path = Path(self.output_dir) / f"{dao_name}.dbio"
        
        # 디렉토리 생성
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return str(file_path)
