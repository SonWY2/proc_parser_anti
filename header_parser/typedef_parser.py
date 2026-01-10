"""
typedef 구조체 파서
C 헤더 파일에서 typedef struct 구문을 파싱합니다.
"""
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class FieldInfo:
    """구조체 필드 정보"""
    name: str                          # 원본 필드명 (snake_case)
    data_type: str                     # C 데이터 타입
    array_size: Optional[str] = None   # 배열 크기 (문자열, 매크로 가능)
    comment: Optional[str] = None      # 주석 (description)
    is_pointer: bool = False           # 포인터 여부


@dataclass
class StructInfo:
    """구조체 정보"""
    name: str                          # 구조체 typedef 이름
    fields: List[FieldInfo] = field(default_factory=list)
    raw_content: str = ""              # 원본 구조체 코드


class TypedefStructParser:
    """
    typedef struct 구문을 파싱하는 클래스
    
    사용 예:
        parser = TypedefStructParser()
        structs = parser.parse(header_content)
    """
    
    # typedef struct { ... } name; 패턴
    TYPEDEF_STRUCT_PATTERN = re.compile(
        r'typedef\s+struct\s*(?:\w+)?\s*\{'  # typedef struct { 또는 typedef struct name {
        r'(.*?)'                              # 구조체 내용
        r'\}\s*(\w+)\s*;',                   # } name;
        re.DOTALL
    )
    
    # 필드 선언 패턴: type name[size]; //comment 또는 type name; //comment
    FIELD_PATTERN = re.compile(
        r'^\s*'
        r'(\w+(?:\s+\w+)?)\s+'               # 타입 (예: char, unsigned int)
        r'(\*?)(\w+)\s*'                      # 포인터 여부 + 필드명
        r'(?:\[\s*([^\]]+)\s*\])?'           # 배열 크기 (선택)
        r'\s*;'                               # 세미콜론
        r'(?:\s*//(.*))?',                   # 주석 (선택)
        re.MULTILINE
    )
    
    def parse(self, content: str) -> Dict[str, StructInfo]:
        """
        헤더 파일 내용을 파싱하여 구조체 정보 추출
        
        Args:
            content: C 헤더 파일 내용
            
        Returns:
            {"struct_name": StructInfo, ...}
        """
        result = {}
        
        for match in self.TYPEDEF_STRUCT_PATTERN.finditer(content):
            struct_body = match.group(1)
            struct_name = match.group(2)
            
            struct_info = StructInfo(
                name=struct_name,
                raw_content=match.group(0)
            )
            
            # 필드 파싱
            for field_match in self.FIELD_PATTERN.finditer(struct_body):
                data_type = field_match.group(1).strip()
                is_pointer = bool(field_match.group(2))
                field_name = field_match.group(3)
                array_size = field_match.group(4)
                comment = field_match.group(5)
                
                # 배열 크기에서 공백 제거
                if array_size:
                    array_size = array_size.strip()
                
                # 주석에서 앞뒤 공백 제거
                if comment:
                    comment = comment.strip()
                
                field_info = FieldInfo(
                    name=field_name,
                    data_type=data_type,
                    array_size=array_size,
                    comment=comment,
                    is_pointer=is_pointer
                )
                struct_info.fields.append(field_info)
            
            result[struct_name] = struct_info
        
        return result
    
    def get_field_names(self, struct_info: StructInfo) -> set:
        """구조체의 모든 필드명 집합 반환"""
        return {f.name for f in struct_info.fields}
