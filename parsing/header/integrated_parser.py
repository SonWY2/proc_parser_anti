"""
CPG 연계 통합 헤더 파서
CPG 모듈과 연계하여 프로그램의 모든 연결된 헤더를 분석합니다.
"""
import os
import sys
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

# 상위 디렉토리를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .classifier import HeaderClassifier, HeaderType, HeaderInfo
from .macro_extractor import MacroExtractor
from .header_parser import HeaderParser
from shared_config.logger import logger, LogStage


@dataclass
class ParseResult:
    """통합 파싱 결과"""
    # 분류된 헤더 정보
    stp_headers: List[HeaderInfo] = field(default_factory=list)
    struct_headers: List[HeaderInfo] = field(default_factory=list)
    macro_headers: List[HeaderInfo] = field(default_factory=list)
    other_headers: List[HeaderInfo] = field(default_factory=list)
    
    # 추출된 데이터
    db_vars_info: Dict[str, Dict] = field(default_factory=dict)
    macros: Dict[str, Any] = field(default_factory=dict)
    struct_info: Dict[str, Any] = field(default_factory=dict)
    
    # 메타 정보
    source_file: str = ""
    total_headers: int = 0
    
    def to_dict(self) -> dict:
        return {
            "source_file": self.source_file,
            "total_headers": self.total_headers,
            "stp_headers": [h.path for h in self.stp_headers],
            "macro_headers": [h.path for h in self.macro_headers],
            "struct_headers": [h.path for h in self.struct_headers],
            "macros": self.macros,
            "db_vars_info_count": len(self.db_vars_info),
        }


class IntegratedHeaderParser:
    """
    CPG 연계 통합 헤더 파서
    
    프로그램 파일(.pc)에서 시작하여 모든 연결된 헤더를 분석합니다.
    
    워크플로우:
    1. CPG로 연결된 모든 헤더 수집
    2. 헤더 타입별 분류 (STP/MACRO/STRUCT 등)
    3. 매크로 헤더에서 상수 추출
    4. STP 헤더 파싱 (매크로 값 주입)
    
    사용 예:
        parser = IntegratedHeaderParser(include_paths=["./include"])
        result = parser.parse_program("program.pc")
        
        print(f"STP 헤더: {result.stp_headers}")
        print(f"매크로: {result.macros}")
        print(f"구조체 정보: {result.db_vars_info}")
    """
    
    def __init__(
        self,
        include_paths: Optional[List[str]] = None,
        verbose: bool = False
    ):
        """
        Args:
            include_paths: 헤더 파일 검색 경로 리스트
            verbose: 상세 로그 출력 여부 (deprecated, logger 사용)
        """
        self.include_paths = include_paths or []
        self.verbose = verbose
        
        # 내부 파서 초기화
        self.classifier = HeaderClassifier()
        self.macro_extractor = MacroExtractor()
        self.header_parser = None  # 매크로 추출 후 초기화
        
        # CPG 모듈 지연 import
        self._cpg_builder = None
    
    @property
    def cpg_builder(self):
        """CPGBuilder 지연 로딩"""
        if self._cpg_builder is None:
            try:
                from CPG import CPGBuilder
                self._cpg_builder = CPGBuilder(
                    include_paths=self.include_paths,
                    verbose=self.verbose
                )
            except ImportError:
                raise ImportError(
                    "CPG 모듈을 찾을 수 없습니다. "
                    "CPG 모듈이 설치되어 있는지 확인하세요."
                )
        return self._cpg_builder
    
    def set_include_paths(self, paths: List[str]):
        """헤더 검색 경로 설정"""
        self.include_paths = paths
        if self._cpg_builder:
            self._cpg_builder.set_include_paths(paths)
    
    def add_include_path(self, path: str):
        """헤더 검색 경로 추가"""
        self.include_paths.append(path)
        if self._cpg_builder:
            self._cpg_builder.add_include_path(path)
    
    def parse_program(
        self,
        pc_file_path: str,
        additional_macros: Optional[Dict[str, Any]] = None,
        count_field_mapping: Optional[Dict[str, str]] = None
    ) -> ParseResult:
        """
        프로그램 파일에서 시작하여 연결된 모든 헤더 분석
        
        Args:
            pc_file_path: Pro*C 프로그램 파일 경로
            additional_macros: 추가 매크로 값 (외부 주입)
            count_field_mapping: count 필드 수동 매핑
            
        Returns:
            ParseResult: 통합 파싱 결과
        """
        result = ParseResult(source_file=pc_file_path)
        
        # 1. CPG로 연결된 헤더 수집
        with LogStage("CPG 분석", file=pc_file_path):
            try:
                cpg = self.cpg_builder.build_from_file(
                    pc_file_path, 
                    follow_includes=True
                )
            except Exception as e:
                logger.warning(f"CPG 분석 실패, 단일 파일 모드로 전환: {e}")
                return self._parse_single_file(
                    pc_file_path, 
                    additional_macros, 
                    count_field_mapping
                )
        
        # 2. 헤더 타입별 분류
        with LogStage("헤더 분류"):
            classified = self.classifier.classify_from_cpg(cpg)
            
            result.stp_headers = classified.get(HeaderType.STP_HEADER, [])
            result.struct_headers = classified.get(HeaderType.STRUCT_HEADER, [])
            result.macro_headers = classified.get(HeaderType.MACRO_HEADER, [])
            result.other_headers = (
                classified.get(HeaderType.FUNCTION_HEADER, []) +
                classified.get(HeaderType.MIXED_HEADER, []) +
                classified.get(HeaderType.UNKNOWN, [])
            )
            
            result.total_headers = sum(len(v) for v in classified.values())
            
            logger.debug(f"STP 헤더: {len(result.stp_headers)}개")
            logger.debug(f"매크로 헤더: {len(result.macro_headers)}개")
            logger.debug(f"구조체 헤더: {len(result.struct_headers)}개")
        
        # 3. 매크로 추출
        with LogStage("매크로 추출"):
            macro_paths = [h.path for h in result.macro_headers]
            mixed_paths = [
                h.path for h in classified.get(HeaderType.MIXED_HEADER, [])
                if h.has_macros
            ]
            all_macro_paths = macro_paths + mixed_paths
            
            result.macros = self.macro_extractor.extract_from_files(all_macro_paths)
            
            if additional_macros:
                result.macros.update(additional_macros)
            
            logger.debug(f"추출된 매크로: {len(result.macros)}개")
        
        # 4. STP 헤더 파싱
        with LogStage("STP 헤더 파싱"):
            numeric_macros = self.macro_extractor.get_numeric_macros(result.macros)
            
            self.header_parser = HeaderParser(
                external_macros=numeric_macros,
                count_field_mapping=count_field_mapping
            )
            
            for header_info in result.stp_headers:
                try:
                    db_vars = self.header_parser.parse_file(header_info.path)
                    result.db_vars_info.update(db_vars)
                    logger.debug(f"파싱 완료: {header_info.path} ({len(db_vars)}개 구조체)")
                except Exception as e:
                    logger.error(f"파싱 실패: {header_info.path} - {e}")
        
        return result
    
    def _parse_single_file(
        self,
        file_path: str,
        additional_macros: Optional[Dict[str, Any]] = None,
        count_field_mapping: Optional[Dict[str, str]] = None
    ) -> ParseResult:
        """
        단일 파일 파싱 (CPG 없이)
        
        헤더 파일이 직접 지정된 경우 사용
        """
        result = ParseResult(source_file=file_path)
        
        # 파일 확장자에 따라 처리
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == '.h':
            # 헤더 파일 직접 파싱
            header_info = self.classifier.classify_file(file_path)
            
            if header_info.header_type == HeaderType.STP_HEADER:
                result.stp_headers.append(header_info)
                
                parser = HeaderParser(
                    external_macros=additional_macros or {},
                    count_field_mapping=count_field_mapping
                )
                result.db_vars_info = parser.parse_file(file_path)
            
            elif header_info.header_type == HeaderType.MACRO_HEADER:
                result.macro_headers.append(header_info)
                result.macros = self.macro_extractor.extract_file(file_path)
        
        result.total_headers = 1
        return result
    
    def parse_headers(
        self,
        header_paths: List[str],
        additional_macros: Optional[Dict[str, Any]] = None,
        count_field_mapping: Optional[Dict[str, str]] = None
    ) -> ParseResult:
        """
        헤더 파일 목록 직접 파싱 (CPG 없이)
        
        Args:
            header_paths: 헤더 파일 경로 리스트
            additional_macros: 추가 매크로 값
            count_field_mapping: count 필드 수동 매핑
            
        Returns:
            ParseResult
        """
        result = ParseResult()
        result.total_headers = len(header_paths)
        
        # 1. 헤더 분류
        for path in header_paths:
            header_info = self.classifier.classify_file(path)
            
            if header_info.header_type == HeaderType.STP_HEADER:
                result.stp_headers.append(header_info)
            elif header_info.header_type == HeaderType.MACRO_HEADER:
                result.macro_headers.append(header_info)
            elif header_info.header_type == HeaderType.STRUCT_HEADER:
                result.struct_headers.append(header_info)
            else:
                result.other_headers.append(header_info)
        
        # 2. 매크로 추출
        macro_paths = [h.path for h in result.macro_headers]
        result.macros = self.macro_extractor.extract_from_files(macro_paths)
        
        if additional_macros:
            result.macros.update(additional_macros)
        
        # 3. STP 헤더 파싱
        numeric_macros = self.macro_extractor.get_numeric_macros(result.macros)
        
        parser = HeaderParser(
            external_macros=numeric_macros,
            count_field_mapping=count_field_mapping
        )
        
        for header_info in result.stp_headers:
            try:
                db_vars = parser.parse_file(header_info.path)
                result.db_vars_info.update(db_vars)
            except Exception:
                pass
        
        return result
