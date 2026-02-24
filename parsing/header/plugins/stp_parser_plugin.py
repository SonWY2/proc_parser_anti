"""
STP 파서 플러그인

STP(Structure Type Protocol) 배열을 파싱하는 플러그인입니다.
"""
import re
from typing import Dict, Any, Optional, List, Tuple

from ..parser_interface import HeaderParserPlugin, HeaderFormatType, ParseContext

# STP 숫자 타입 (size/decimal 업데이트 대상)
STP_NUMERIC_TYPES = {'i', 'o', 'd', 'l', 'g', 's', 'c'}


class STPParserPlugin(HeaderParserPlugin):
    """
    STP 배열 파싱 플러그인
    
    STP(Structure Type Protocol) 배열은 구조체 필드의 메타데이터를 정의합니다.
    형식: xxx_stp = { 't', v1, v2, v3, ... }
    
    - t: 타입 코드 (i, o, d, l, g, s, c, w 등)
    - v1: size
    - v2: decimal (0이 아닐 때만 업데이트)
    - v3: reserved
    """
    
    # STP 배열 패턴: int name_stp[] = { ... };
    STP_PATTERN = re.compile(
        r'int\s+(\w+_stp)\s*\[\s*\]\s*=\s*\{'
        r'(.*?)'
        r'\}\s*;',
        re.DOTALL
    )
    
    # 단일 초기화 항목 패턴 (4개씩 그룹)
    # 형식: 't', v1, v2, v3 또는 'x', v1, v2, v3
    ITEM_PATTERN = re.compile(
        r"'([^'\\]|\\0)'\s*,\s*"  # 타입 코드 (문자)
        r'(\d+)\s*,\s*'           # v1 (size)
        r'(\d+)\s*,\s*'           # v2 (decimal)
        r'(\d+)'                  # v3 (reserved)
    )
    
    @property
    def format_type(self) -> HeaderFormatType:
        return HeaderFormatType.STP
    
    @property
    def priority(self) -> int:
        return 20  # typedef 파싱 후 실행
    
    def can_parse(self, content: str) -> bool:
        return '_stp[]' in content or bool(re.search(r'\w+_stp\s*\[', content))
    
    def parse(self, content: str, context: Optional[ParseContext] = None) -> Dict[str, Any]:
        """STP 배열 파싱"""
        stp_data = {}
        
        for match in self.STP_PATTERN.finditer(content):
            stp_name = match.group(1)  # xxx_stp
            stp_body = match.group(2)
            
            items = []
            for item_match in self.ITEM_PATTERN.finditer(stp_body):
                type_code = item_match.group(1)
                # \0 처리
                if type_code == '\\0':
                    type_code = '\0'
                    
                v1 = int(item_match.group(2))
                v2 = int(item_match.group(3))
                v3 = int(item_match.group(4))
                
                items.append((type_code, v1, v2, v3))
            
            stp_data[stp_name] = items
        
        return {"stp_data": stp_data}
    
    @staticmethod
    def get_struct_name(stp_name: str) -> str:
        """
        STP 이름에서 구조체 이름 추출
        
        Args:
            stp_name: STP 배열 이름 (예: spaa010p_in_stp)
            
        Returns:
            구조체 이름 (예: spaa010p_in_t)
        """
        if stp_name.endswith('_stp'):
            return stp_name[:-4] + '_t'
        return stp_name
    
    @staticmethod
    def update_variables(
        variables: Dict[str, Dict],
        stp_items: List[Tuple],
        skip_wrapper: bool = True
    ) -> Dict[str, Dict]:
        """
        STP 정보를 사용하여 변수 정보의 size/decimal 업데이트
        
        Args:
            variables: 변수 정보 딕셔너리 (camelCase 키)
            stp_items: STP 항목 리스트 [(type, v1, v2, v3), ...]
            skip_wrapper: 'w' 타입 스킵 여부
            
        Returns:
            업데이트된 변수 정보 딕셔너리
        """
        var_list = list(variables.keys())
        stp_idx = 0
        var_idx = 0
        
        while var_idx < len(var_list) and stp_idx < len(stp_items):
            type_code, v1, v2, v3 = stp_items[stp_idx]
            
            # 종료 마커
            if type_code in ('\0', '0'):
                break
            
            # wrapper 타입 스킵
            if skip_wrapper and type_code == 'w':
                stp_idx += 1
                continue
            
            # g 타입도 스킵 (그룹 카운터)
            if type_code == 'g':
                stp_idx += 1
                continue
            
            var_name = var_list[var_idx]
            
            # 숫자 타입만 size/decimal 업데이트
            if type_code in STP_NUMERIC_TYPES:
                try:
                    variables[var_name]["size"] = v1
                except Exception:
                    pass
                
                try:
                    if v2:  # v2가 0이 아닐 때만
                        variables[var_name]["decimal"] = v2
                except Exception:
                    pass
            
            stp_idx += 1
            var_idx += 1
        
        return variables
