"""
함수별 아티팩트 생성기

특정 함수에서 사용하는 SQL, 변수를 기반으로
MyBatis XML, OMM, DBIO, DAO 코드를 생성합니다.
"""
from typing import Dict, List, Optional
import re


class FunctionArtifactGenerator:
    """
    함수별 MyBatis/OMM/DBIO/DAO 코드 생성
    
    기존 omm_generator, dbio_generator, dao_generator 모듈을 활용하여
    특정 함수의 SQL/변수만으로 아티팩트를 생성합니다.
    """
    
    def __init__(self, base_package: str = "com.example"):
        """
        Args:
            base_package: 생성될 Java 클래스의 기본 패키지
        """
        self.base_package = base_package
        
        # 기존 생성기 로드 시도
        self._omm_generator = None
        self._dbio_generator = None
        self._dao_generator = None
        self._load_generators()
    
    def _load_generators(self):
        """기존 생성기 모듈 로드"""
        try:
            from omm_generator import OMMGenerator
            self._omm_generator = OMMGenerator(base_package=self.base_package)
        except ImportError:
            pass
        
        try:
            from dbio_generator import DBIOGenerator
            self._dbio_generator = DBIOGenerator(base_package=self.base_package)
        except ImportError:
            pass
        
        try:
            from dao_generator import DAOGenerator
            self._dao_generator = DAOGenerator(base_package=self.base_package)
        except ImportError:
            pass
    
    def _to_camel_case(self, name: str) -> str:
        """snake_case → camelCase"""
        components = name.split('_')
        return components[0].lower() + ''.join(x.title() for x in components[1:])
    
    def _to_pascal_case(self, name: str) -> str:
        """snake_case → PascalCase"""
        components = name.split('_')
        return ''.join(x.title() for x in components)
    
    def generate_mybatis_xml(
        self, 
        sql_elements: List[Dict], 
        namespace: str = "mapper"
    ) -> str:
        """
        SQL 목록 → MyBatis XML 스니펫
        
        Args:
            sql_elements: SQL 요소 목록
            namespace: MyBatis mapper namespace
            
        Returns:
            MyBatis XML 문자열
        """
        if not sql_elements:
            return ""
        
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN"',
            '  "http://mybatis.org/dtd/mybatis-3-mapper.dtd">',
            f'<mapper namespace="{namespace}">',
            ''
        ]
        
        for sql in sql_elements:
            sql_id = sql.get("sql_id", sql.get("id", "unknown"))
            sql_type = sql.get("sql_type", "select").lower()
            mybatis_sql = sql.get("mybatis_sql") or sql.get("standardized_sql", "")
            
            # SQL 타입에 따른 MyBatis 태그 결정
            if sql_type in ("select", "declare_cursor", "fetch"):
                tag = "select"
                result_type = sql.get("result_type", "map")
                lines.append(f'  <{tag} id="{sql_id}" resultType="{result_type}">')
            elif sql_type == "insert":
                tag = "insert"
                lines.append(f'  <{tag} id="{sql_id}">')
            elif sql_type == "update":
                tag = "update"
                lines.append(f'  <{tag} id="{sql_id}">')
            elif sql_type == "delete":
                tag = "delete"
                lines.append(f'  <{tag} id="{sql_id}">')
            else:
                # 기타 SQL (COMMIT, ROLLBACK 등)은 주석으로 처리
                lines.append(f'  <!-- {sql_type}: {sql_id} -->')
                continue
            
            # SQL 본문 (들여쓰기)
            for line in mybatis_sql.strip().split('\n'):
                lines.append(f'    {line}')
            
            lines.append(f'  </{tag}>')
            lines.append('')
        
        lines.append('</mapper>')
        
        return '\n'.join(lines)
    
    def generate_omm(
        self, 
        function_name: str,
        variables: List[Dict]
    ) -> str:
        """
        변수 목록 → OMM VO 클래스
        
        Args:
            function_name: 함수명 (클래스명 생성에 사용)
            variables: 변수 요소 목록
            
        Returns:
            Java VO 클래스 코드
        """
        if not variables:
            return ""
        
        class_name = self._to_pascal_case(function_name) + "VO"
        
        lines = [
            f'package {self.base_package}.vo;',
            '',
            'import java.io.Serializable;',
            '',
            '/**',
            f' * {function_name} 함수용 VO 클래스',
            ' */',
            f'public class {class_name} implements Serializable {{',
            '',
            '    private static final long serialVersionUID = 1L;',
            ''
        ]
        
        # 필드 생성
        for var in variables:
            var_name = var.get("name", "")
            var_type = var.get("data_type", "String")
            java_type = self._c_type_to_java(var_type)
            field_name = self._to_camel_case(var_name)
            
            lines.append(f'    private {java_type} {field_name};')
        
        lines.append('')
        
        # Getter/Setter 생성
        for var in variables:
            var_name = var.get("name", "")
            var_type = var.get("data_type", "String")
            java_type = self._c_type_to_java(var_type)
            field_name = self._to_camel_case(var_name)
            method_name = self._to_pascal_case(var_name)
            
            # Getter
            lines.append(f'    public {java_type} get{method_name}() {{')
            lines.append(f'        return this.{field_name};')
            lines.append('    }')
            lines.append('')
            
            # Setter
            lines.append(f'    public void set{method_name}({java_type} {field_name}) {{')
            lines.append(f'        this.{field_name} = {field_name};')
            lines.append('    }')
            lines.append('')
        
        lines.append('}')
        
        return '\n'.join(lines)
    
    def generate_dbio(
        self, 
        function_name: str, 
        sql_elements: List[Dict]
    ) -> str:
        """
        SQL 목록 → DBIO 클래스
        
        Args:
            function_name: 함수명
            sql_elements: SQL 요소 목록
            
        Returns:
            Java DBIO 클래스 코드
        """
        if not sql_elements:
            return ""
        
        class_name = self._to_pascal_case(function_name) + "DBIO"
        
        lines = [
            f'package {self.base_package}.dbio;',
            '',
            'import org.springframework.stereotype.Repository;',
            'import org.apache.ibatis.annotations.Mapper;',
            '',
            '/**',
            f' * {function_name} 함수용 DBIO 클래스',
            ' */',
            '@Repository',
            f'public class {class_name} {{',
            '',
            '    @Autowired',
            f'    private {self._to_pascal_case(function_name)}Mapper mapper;',
            ''
        ]
        
        for sql in sql_elements:
            sql_id = sql.get("sql_id", sql.get("id", "unknown"))
            sql_type = sql.get("sql_type", "select").lower()
            method_name = self._to_camel_case(sql_id)
            
            if sql_type in ("select", "declare_cursor", "fetch"):
                lines.append(f'    public Object {method_name}() {{')
                lines.append(f'        return mapper.{method_name}();')
                lines.append('    }')
            elif sql_type in ("insert", "update", "delete"):
                lines.append(f'    public int {method_name}() {{')
                lines.append(f'        return mapper.{method_name}();')
                lines.append('    }')
            
            lines.append('')
        
        lines.append('}')
        
        return '\n'.join(lines)
    
    def generate_dao(
        self, 
        function_name: str, 
        sql_elements: List[Dict]
    ) -> str:
        """
        SQL 목록 → DAO 인터페이스 (MyBatis Mapper)
        
        Args:
            function_name: 함수명
            sql_elements: SQL 요소 목록
            
        Returns:
            Java DAO 인터페이스 코드
        """
        if not sql_elements:
            return ""
        
        class_name = self._to_pascal_case(function_name) + "Mapper"
        
        lines = [
            f'package {self.base_package}.dao;',
            '',
            'import org.apache.ibatis.annotations.Mapper;',
            'import java.util.List;',
            'import java.util.Map;',
            '',
            '/**',
            f' * {function_name} 함수용 MyBatis Mapper 인터페이스',
            ' */',
            '@Mapper',
            f'public interface {class_name} {{',
            ''
        ]
        
        for sql in sql_elements:
            sql_id = sql.get("sql_id", sql.get("id", "unknown"))
            sql_type = sql.get("sql_type", "select").lower()
            method_name = self._to_camel_case(sql_id)
            
            if sql_type in ("select", "declare_cursor", "fetch"):
                lines.append(f'    List<Map<String, Object>> {method_name}();')
            elif sql_type == "insert":
                lines.append(f'    int {method_name}();')
            elif sql_type == "update":
                lines.append(f'    int {method_name}();')
            elif sql_type == "delete":
                lines.append(f'    int {method_name}();')
            
            lines.append('')
        
        lines.append('}')
        
        return '\n'.join(lines)
    
    def _c_type_to_java(self, c_type: str) -> str:
        """C 타입을 Java 타입으로 변환"""
        type_map = {
            "char": "String",
            "varchar": "String",
            "int": "Integer",
            "long": "Long",
            "short": "Short",
            "float": "Float",
            "double": "Double",
            "decimal": "java.math.BigDecimal",
        }
        
        c_type_lower = c_type.lower().strip()
        
        for c, java in type_map.items():
            if c in c_type_lower:
                return java
        
        return "String"
