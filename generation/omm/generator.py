"""
OMM 파일 생성기
db_vars_info 구조를 OMM 파일로 변환합니다.
"""
import os
from typing import Dict, List, Optional, Any
from pathlib import Path
import sys

# 상위 디렉토리를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared_config import struct_name_to_class_name


class OMMGenerator:
    """
    OMM 파일 생성 클래스
    
    db_vars_info 구조를 받아 OMM 파일 내용을 생성합니다.
    
    OMM 파일 포맷:
        OMM {package}.{ClassName}
        < logicalName="{name}" description="{description}" >
        {
            {JavaType} {fieldName} < length={size} description="{desc}" > ;
        }
    
    사용 예:
        generator = OMMGenerator(base_package="com.example.dao.dto")
        content = generator.generate(db_vars_info, "spaa010p_inrec1")
    """
    
    def __init__(
        self,
        base_package: str,
        output_dir: Optional[str] = None
    ):
        """
        Args:
            base_package: Java 패키지 루트 (예: "com.example.dao.dto")
            output_dir: 출력 디렉토리 (파일 저장할 경우)
        """
        self.base_package = base_package
        self.output_dir = output_dir
    
    def generate(
        self,
        db_vars_info: Dict[str, Dict],
        struct_name: str,
        logical_name: Optional[str] = None,
        description: Optional[str] = None
    ) -> str:
        """
        단일 구조체의 OMM 파일 내용 생성
        
        Args:
            db_vars_info: 구조체 변수 정보
                {
                    "fieldName": {
                        "dtype": "String",
                        "size": 8,
                        "decimal": 0,
                        "description": "필드 설명",
                        ...
                    }
                }
            struct_name: 구조체 이름 (예: "spaa010p_inrec1")
            logical_name: 논리명 (없으면 클래스명 사용)
            description: 설명 (없으면 클래스명 사용)
            
        Returns:
            OMM 파일 내용 문자열
        """
        class_name = struct_name_to_class_name(struct_name)
        full_class_path = f"{self.base_package}.{class_name}"
        
        logical_name = logical_name or class_name
        description = description or class_name
        
        lines = []
        
        # 헤더
        lines.append(f"OMM {full_class_path}")
        lines.append(f'< logicalName= "{logical_name}" description="{description}"')
        lines.append(">")
        lines.append("{")
        
        # 필드들
        for field_name, field_info in db_vars_info.items():
            field_line = self._generate_field(field_name, field_info)
            lines.append(f"\t{field_line}")
        
        lines.append("}")
        
        return "\r\n".join(lines)
    
    def _generate_field(self, field_name: str, field_info: Dict) -> str:
        """
        단일 필드의 OMM 라인 생성
        
        Args:
            field_name: 필드명 (camelCase)
            field_info: 필드 정보 딕셔너리
            
        Returns:
            OMM 필드 라인 문자열
        """
        dtype = field_info.get("dtype", "String")
        size = field_info.get("size", 9)
        decimal = field_info.get("decimal", 0)
        description = field_info.get("description", "")
        array_size = field_info.get("arraySize")
        array_ref = field_info.get("arrayReference")
        struct_type = field_info.get("structType")
        
        # 타입 결정 (구조체 참조인 경우 전체 경로)
        if struct_type:
            type_str = f"{self.base_package}.{struct_name_to_class_name(struct_type)}"
        else:
            type_str = dtype
        
        # 속성 구성
        attrs = []
        attrs.append(f"length = {size}")
        
        if decimal:
            attrs.append(f"decimal = {decimal}")
        
        if array_ref:
            attrs.append(f'arrayReference = "{array_ref}"')
        
        if description:
            # description에서 특수문자 이스케이프
            desc_escaped = description.replace('"', '\\"')
            attrs.append(f'description = "{desc_escaped}"')
        
        attrs_str = " ".join(attrs)
        
        return f"{type_str} {field_name} < {attrs_str} > ;"
    
    def generate_all(
        self,
        all_structs: Dict[str, Dict[str, Dict]]
    ) -> Dict[str, str]:
        """
        모든 구조체의 OMM 파일 내용 생성
        
        Args:
            all_structs: {struct_name: db_vars_info, ...}
            
        Returns:
            {struct_name: omm_content, ...}
        """
        result = {}
        for struct_name, db_vars_info in all_structs.items():
            result[struct_name] = self.generate(db_vars_info, struct_name)
        return result
    
    def write(self, content: str, struct_name: str) -> str:
        """
        OMM 내용을 파일로 저장
        
        Args:
            content: OMM 파일 내용
            struct_name: 구조체 이름
            
        Returns:
            저장된 파일 경로
        """
        if not self.output_dir:
            raise ValueError("output_dir가 설정되지 않았습니다")
        
        class_name = struct_name_to_class_name(struct_name)
        file_path = Path(self.output_dir) / f"{class_name}.omm"
        
        # 디렉토리 생성
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return str(file_path)
    
    def write_all(
        self,
        all_structs: Dict[str, Dict[str, Dict]]
    ) -> Dict[str, str]:
        """
        모든 구조체의 OMM 파일 저장
        
        Returns:
            {struct_name: file_path, ...}
        """
        result = {}
        for struct_name, db_vars_info in all_structs.items():
            content = self.generate(db_vars_info, struct_name)
            file_path = self.write(content, struct_name)
            result[struct_name] = file_path
        return result
