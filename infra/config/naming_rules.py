"""
네이밍 규칙 설정
필드명 변환, count 필드 탐지 패턴 등을 관리합니다.
"""
import re
from typing import Optional, List, Set

# =============================================================================
# count 필드 탐지 패턴 (우선순위 순)
# =============================================================================
COUNT_FIELD_PATTERNS = [
    "{field_name}_count",   # outrec1_count
    "{field_name}_cnt",     # outrec1_cnt
    "{field_name}Count",    # outrec1Count (이미 camelCase)
    "{field_name}Cnt",      # outrec1Cnt
]

# =============================================================================
# 기본 타입 (커스텀 구조체 판별용)
# =============================================================================
PRIMITIVE_TYPES = {
    "int", "char", "long", "double", "float", "short", "void",
    "unsigned int", "unsigned long", "unsigned short", "unsigned char",
    "signed int", "signed long", "signed short", "signed char",
}


# =============================================================================
# 헬퍼 함수
# =============================================================================

def snake_to_camel(name: str) -> str:
    """
    snake_case를 camelCase로 변환
    
    Examples:
        user_name -> userName
        rfrn_strt_date -> rfrnStrtDate
        a_nxt_sqno -> aNxtSqno
    """
    if not name:
        return name
    
    components = name.split('_')
    # 첫 번째 컴포넌트는 소문자 유지, 나머지는 첫 글자 대문자
    return components[0].lower() + ''.join(x.title() for x in components[1:])


def camel_to_pascal(name: str) -> str:
    """
    camelCase를 PascalCase로 변환
    
    Examples:
        userName -> UserName
        rfrnStrtDate -> RfrnStrtDate
    """
    if not name:
        return name
    return name[0].upper() + name[1:]


def find_count_field(
    array_field_name: str,
    struct_fields: Set[str],
    manual_mapping: Optional[dict] = None
) -> Optional[str]:
    """
    배열 필드에 해당하는 count 필드를 찾습니다.
    
    Args:
        array_field_name: 배열 필드명 (snake_case)
        struct_fields: 구조체의 모든 필드명 집합
        manual_mapping: 수동 매핑 딕셔너리 (선택)
        
    Returns:
        count 필드명 (camelCase) 또는 None
    """
    # 1. 수동 매핑 확인
    if manual_mapping and array_field_name in manual_mapping:
        return snake_to_camel(manual_mapping[array_field_name])
    
    # 2. 패턴 매칭 시도
    for pattern in COUNT_FIELD_PATTERNS:
        candidate = pattern.format(field_name=array_field_name)
        if candidate in struct_fields:
            return snake_to_camel(candidate)
    
    # 3. 매칭 실패
    return None


def is_primitive_type(type_name: str) -> bool:
    """기본 타입인지 확인"""
    return type_name.lower().strip() in PRIMITIVE_TYPES


def is_custom_struct(type_name: str) -> bool:
    """커스텀 구조체인지 확인 (기본 타입이 아니면 구조체로 간주)"""
    return not is_primitive_type(type_name)


def struct_name_to_class_name(struct_name: str) -> str:
    """
    구조체명을 Java 클래스명으로 변환
    
    Examples:
        spaa010p_inrec1 -> Spaa010pInrec1
        user_info_t -> UserInfoT
    """
    # snake_case를 PascalCase로
    components = struct_name.split('_')
    return ''.join(x.title() for x in components)
