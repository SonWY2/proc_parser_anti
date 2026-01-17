"""
헤더 파일 타입 분류기
헤더 파일의 내용을 분석하여 타입을 분류합니다.
"""
import re
import os
from enum import Enum
from typing import Dict, List, Optional, Set
from dataclasses import dataclass


class HeaderType(Enum):
    """헤더 파일 타입"""
    STP_HEADER = "stp"          # 전문 헤더 (_stp[] 배열 + typedef 구조체)
    STRUCT_HEADER = "struct"    # 구조체만 있는 헤더
    MACRO_HEADER = "macro"      # 매크로/상수 헤더
    FUNCTION_HEADER = "func"    # 함수 선언 헤더
    MIXED_HEADER = "mixed"      # 혼합 헤더
    SYSTEM_HEADER = "system"    # 시스템 헤더
    UNKNOWN = "unknown"         # 분류 불가


@dataclass
class HeaderInfo:
    """헤더 파일 정보"""
    path: str
    header_type: HeaderType
    has_stp: bool = False
    has_typedef: bool = False
    has_macros: bool = False
    has_functions: bool = False
    macro_count: int = 0
    struct_count: int = 0
    
    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "type": self.header_type.value,
            "has_stp": self.has_stp,
            "has_typedef": self.has_typedef,
            "has_macros": self.has_macros,
            "has_functions": self.has_functions,
            "macro_count": self.macro_count,
            "struct_count": self.struct_count,
        }


class HeaderClassifier:
    """
    헤더 파일 타입 분류기
    
    헤더 파일의 내용을 분석하여 다음 타입으로 분류합니다:
    - STP_HEADER: _stp[] 배열과 typedef 구조체를 포함하는 전문 헤더
    - STRUCT_HEADER: typedef 구조체만 포함
    - MACRO_HEADER: #define 매크로만 포함
    - FUNCTION_HEADER: 함수 선언만 포함
    - MIXED_HEADER: 여러 타입 혼합
    - SYSTEM_HEADER: 시스템 헤더 (<...> 형태)
    
    사용 예:
        classifier = HeaderClassifier()
        header_type = classifier.classify_file("sample.h")
    """
    
    # 패턴 정의
    STP_PATTERN = re.compile(r'\w+_stp\s*\[\s*\]', re.MULTILINE)
    TYPEDEF_STRUCT_PATTERN = re.compile(r'typedef\s+struct', re.MULTILINE)
    MACRO_PATTERN = re.compile(r'^\s*#\s*define\s+(\w+)', re.MULTILINE)
    FUNCTION_DECL_PATTERN = re.compile(
        r'^\s*(?:extern\s+)?(?:static\s+)?'
        r'(?:unsigned\s+|signed\s+)?'
        r'(?:void|int|char|long|short|double|float|\w+)\s*\*?\s+'
        r'(\w+)\s*\([^)]*\)\s*;',
        re.MULTILINE
    )
    
    def __init__(self):
        self._cache: Dict[str, HeaderInfo] = {}
    
    def classify(self, content: str, file_path: str = "<unknown>") -> HeaderInfo:
        """
        헤더 내용으로 타입 분류
        
        Args:
            content: 헤더 파일 내용
            file_path: 파일 경로 (정보용)
            
        Returns:
            HeaderInfo: 헤더 정보
        """
        has_stp = bool(self.STP_PATTERN.search(content))
        has_typedef = bool(self.TYPEDEF_STRUCT_PATTERN.search(content))
        has_macros = bool(self.MACRO_PATTERN.search(content))
        has_functions = bool(self.FUNCTION_DECL_PATTERN.search(content))
        
        macro_count = len(self.MACRO_PATTERN.findall(content))
        struct_count = len(self.TYPEDEF_STRUCT_PATTERN.findall(content))
        
        # 타입 결정
        header_type = self._determine_type(
            has_stp, has_typedef, has_macros, has_functions
        )
        
        return HeaderInfo(
            path=file_path,
            header_type=header_type,
            has_stp=has_stp,
            has_typedef=has_typedef,
            has_macros=has_macros,
            has_functions=has_functions,
            macro_count=macro_count,
            struct_count=struct_count,
        )
    
    def _determine_type(
        self,
        has_stp: bool,
        has_typedef: bool,
        has_macros: bool,
        has_functions: bool
    ) -> HeaderType:
        """타입 결정 로직"""
        
        # STP 배열이 있으면 전문 헤더
        if has_stp:
            return HeaderType.STP_HEADER
        
        # 여러 특성이 혼합된 경우
        features = sum([has_typedef, has_macros, has_functions])
        if features > 1:
            return HeaderType.MIXED_HEADER
        
        # 단일 특성
        if has_typedef:
            return HeaderType.STRUCT_HEADER
        if has_macros:
            return HeaderType.MACRO_HEADER
        if has_functions:
            return HeaderType.FUNCTION_HEADER
        
        return HeaderType.UNKNOWN
    
    def classify_file(self, file_path: str) -> HeaderInfo:
        """
        파일 경로로 타입 분류
        
        Args:
            file_path: 헤더 파일 경로
            
        Returns:
            HeaderInfo: 헤더 정보
        """
        # 캐시 확인
        abs_path = os.path.abspath(file_path)
        if abs_path in self._cache:
            return self._cache[abs_path]
        
        # 시스템 헤더 체크
        if self._is_system_header(file_path):
            info = HeaderInfo(
                path=file_path,
                header_type=HeaderType.SYSTEM_HEADER
            )
            self._cache[abs_path] = info
            return info
        
        # 파일 읽기 및 분류
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            info = self.classify(content, file_path)
            self._cache[abs_path] = info
            return info
        except Exception as e:
            info = HeaderInfo(
                path=file_path,
                header_type=HeaderType.UNKNOWN
            )
            return info
    
    def _is_system_header(self, header_name: str) -> bool:
        """시스템 헤더 여부 확인"""
        system_headers = {
            'stdio.h', 'stdlib.h', 'string.h', 'math.h',
            'time.h', 'ctype.h', 'errno.h', 'signal.h',
            'stdarg.h', 'stddef.h', 'limits.h', 'float.h',
        }
        basename = os.path.basename(header_name)
        return basename in system_headers
    
    def classify_from_cpg(self, cpg) -> Dict[HeaderType, List[HeaderInfo]]:
        """
        CPG의 모든 헤더 분류
        
        Args:
            cpg: CPG 객체 (CPG 모듈에서)
            
        Returns:
            타입별 헤더 정보 딕셔너리
        """
        from CPG.models import NodeType
        
        result: Dict[HeaderType, List[HeaderInfo]] = {
            header_type: [] for header_type in HeaderType
        }
        
        # HEADER 노드 추출
        header_nodes = cpg.get_nodes_by_type(NodeType.HEADER)
        
        for node in header_nodes:
            file_path = node.file_path
            if file_path:
                info = self.classify_file(file_path)
                result[info.header_type].append(info)
        
        return result
    
    def clear_cache(self):
        """캐시 초기화"""
        self._cache.clear()
