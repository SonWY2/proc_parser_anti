"""
헤더 파서 메인 클래스
typedef 구조체와 STP 정보를 통합하여 db_vars_info 구조를 생성합니다.
"""
import os
import sys
from typing import Dict, List, Optional, Any

# 상위 디렉토리를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .typedef_parser import TypedefStructParser, StructInfo, FieldInfo
from .stp_parser import STPParser
from shared_config import (
    get_java_type,
    snake_to_camel,
    camel_to_pascal,
    find_count_field,
    is_custom_struct,
    PRIMITIVE_TYPES,
)
from shared_config.logger import logger


class HeaderParser:
    """
    C 헤더 파일 파서 메인 클래스
    
    typedef 구조체와 STP 배열 정보를 통합하여
    OMM 생성에 필요한 db_vars_info 구조를 생성합니다.
    
    사용 예:
        parser = HeaderParser()
        result = parser.parse_file("sample.h")
        # 또는
        result = parser.parse(header_content)
    """
    
    def __init__(
        self,
        external_macros: Optional[Dict[str, int]] = None,
        count_field_mapping: Optional[Dict[str, str]] = None
    ):
        """
        Args:
            external_macros: 외부 매크로 값 딕셔너리 (예: {"MAX_SIZE": 30})
            count_field_mapping: count 필드 수동 매핑 (예: {"outrec1": "total_count"})
        """
        self.typedef_parser = TypedefStructParser()
        self.stp_parser = STPParser()
        self.external_macros = external_macros or {}
        self.count_field_mapping = count_field_mapping or {}
        logger.debug(f"HeaderParser 초기화 (macros: {len(self.external_macros)}개)")
    
    def parse_file(self, file_path: str) -> Dict[str, Dict]:
        """
        헤더 파일을 읽어서 파싱
        
        Args:
            file_path: C 헤더 파일 경로
            
        Returns:
            db_vars_info 구조
        """
        logger.info(f"헤더 파싱 시작: {file_path}")
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        result = self.parse(content)
        logger.success(f"헤더 파싱 완료: {file_path} ({len(result)}개 구조체)")
        return result
    
    def parse(self, content: str) -> Dict[str, Dict]:
        """
        헤더 파일 내용을 파싱하여 db_vars_info 구조 생성
        
        Args:
            content: C 헤더 파일 내용
            
        Returns:
            {
                "struct_name_t": {
                    "fieldName": {
                        "dtype": "String",
                        "size": 8,
                        "decimal": 0,
                        "name": "field_name",
                        "org_name": "field_name",
                        "description": "필드 설명",
                        "arraySize": 30,         # 배열인 경우
                        "arrayReference": "fieldCountName"  # count 필드 있는 경우
                    },
                    ...
                },
                ...
            }
        """
        # 1. typedef 구조체 파싱
        structs = self.typedef_parser.parse(content)
        
        # 2. STP 배열 파싱
        stp_data = self.stp_parser.parse(content)
        
        # 3. 구조체별로 db_vars_info 생성
        result = {}
        
        for struct_name, struct_info in structs.items():
            # 구조체의 모든 필드명 집합 (count 필드 탐지용)
            field_names = self.typedef_parser.get_field_names(struct_info)
            
            # 필드 정보 변환
            variables = {}
            for field in struct_info.fields:
                camel_name = snake_to_camel(field.name)
                java_type = self._get_field_java_type(field)
                
                var_info = {
                    "dtype": java_type,
                    "size": self._resolve_array_size(field.array_size),
                    "decimal": 0,
                    "name": field.name,
                    "org_name": field.name,
                }
                
                # description (주석에서)
                if field.comment:
                    var_info["description"] = field.comment
                
                # 배열 처리 (커스텀 구조체인 경우)
                if field.array_size and is_custom_struct(field.data_type):
                    var_info["arraySize"] = self._resolve_array_size(field.array_size)
                    
                    # count 필드 탐지
                    count_field = find_count_field(
                        field.name,
                        field_names,
                        self.count_field_mapping
                    )
                    if count_field:
                        var_info["arrayReference"] = count_field
                    
                    # 구조체 타입 저장
                    var_info["structType"] = field.data_type
                
                variables[camel_name] = var_info
            
            # 4. STP 정보로 size/decimal 업데이트
            stp_name = struct_name.replace('_t', '_stp')
            if stp_name in stp_data:
                self.stp_parser.update_variables(variables, stp_data[stp_name])
            
            result[struct_name] = variables
        
        return result
    
    def _get_field_java_type(self, field: FieldInfo) -> str:
        """필드의 Java 타입 결정"""
        # 기본 타입인 경우
        if field.data_type in PRIMITIVE_TYPES or field.data_type.lower() in PRIMITIVE_TYPES:
            return get_java_type(field.data_type.lower())
        
        # 커스텀 구조체인 경우 - PascalCase로 변환
        return camel_to_pascal(snake_to_camel(field.data_type))
    
    def _resolve_array_size(self, size_expr: Optional[str]) -> int:
        """배열 크기 표현식을 정수로 변환"""
        if not size_expr:
            return 9  # 기본값
        
        # 순수 숫자
        try:
            # "8 + 1" 같은 표현식 계산
            cleaned = size_expr.replace(' ', '')
            return eval(cleaned)
        except:
            pass
        
        # 매크로 치환 시도
        for macro, value in self.external_macros.items():
            if macro in size_expr:
                try:
                    replaced = size_expr.replace(macro, str(value))
                    return eval(replaced)
                except:
                    pass
        
        return 9  # 실패 시 기본값
