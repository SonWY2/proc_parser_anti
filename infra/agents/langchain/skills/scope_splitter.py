"""
Scope Splitter Skill

소스 코드를 extern 영역과 함수 단위로 분할하는 Skill입니다.
tree-sitter를 활용하여 정확한 코드 영역을 추출합니다.
"""

from typing import Any, Dict, List, Optional
import logging

from .skill_interface import BaseSkill, SkillResult

logger = logging.getLogger(__name__)


class ScopeSplitterSkill(BaseSkill):
    """
    소스 코드 스코프 분할 Skill
    
    Pro*C 소스 코드를 extern 영역(전역)과 함수 단위로 분할합니다.
    tree-sitter가 사용 가능하면 활용하고, 없으면 metadata 기반 폴백을 사용합니다.
    
    Input:
        {
            "source_code": str,          # 원본 소스 코드
            "metadata": dict,            # 파싱된 메타데이터
            "extern_region": dict,       # (선택) 미리 추출된 extern 영역
            "parsed_functions": list     # (선택) 미리 추출된 함수 목록
        }
        
    Output:
        [
            {
                "scope": "extern" | "function_{name}",
                "code": str,
                "elements": [...],
                "line_range": (start, end)
            },
            ...
        ]
    """
    
    DEFAULT_FUNC_LINE_RANGE = 50  # tree-sitter 없을 때 함수 라인 범위 기본값
    
    def __init__(self):
        self._extractor = None
    
    @property
    def name(self) -> str:
        return "scope_splitter"
    
    @property
    def description(self) -> str:
        return "소스 코드를 extern/function 스코프로 분할"
    
    def _get_extractor(self):
        """tree-sitter extractor 지연 초기화"""
        if self._extractor is None:
            try:
                from parsing.sql.tree_sitter_extractor import get_tree_sitter_extractor
                self._extractor = get_tree_sitter_extractor()
            except ImportError:
                logger.warning("tree-sitter extractor를 로드할 수 없습니다")
        return self._extractor
    
    def validate_input(self, input_data: Any) -> Optional[str]:
        if not isinstance(input_data, dict):
            return "입력은 딕셔너리여야 합니다"
        if "source_code" not in input_data:
            return "source_code 필드가 필요합니다"
        return None
    
    def invoke(self, input_data: Any) -> SkillResult:
        """
        소스 코드를 스코프 단위로 분할
        
        Args:
            input_data: {source_code, metadata, extern_region?, parsed_functions?}
            
        Returns:
            SkillResult with chunks list
        """
        error = self.validate_input(input_data)
        if error:
            return SkillResult(success=False, errors=[error])
        
        source_code = input_data["source_code"]
        metadata = input_data.get("metadata", {})
        extern_region = input_data.get("extern_region", {})
        parsed_functions = input_data.get("parsed_functions", [])
        
        try:
            # State에서 미리 추출된 데이터가 있으면 사용
            if extern_region.get("code") or parsed_functions:
                chunks = self._split_from_cache(
                    source_code, metadata, extern_region, parsed_functions
                )
            else:
                # tree-sitter 사용 시도
                chunks = self._split_with_tree_sitter(source_code, metadata)
                
                if not chunks:
                    # 폴백: metadata 기반 분할
                    chunks = self._split_fallback(source_code, metadata)
            
            return SkillResult(
                success=True, 
                data={"chunks": chunks, "count": len(chunks)}
            )
            
        except Exception as e:
            logger.exception(f"스코프 분할 실패: {e}")
            return SkillResult(success=False, errors=[str(e)])
    
    def _split_from_cache(
        self,
        source_code: str,
        metadata: Dict,
        extern_region: Dict,
        parsed_functions: List[Dict]
    ) -> List[Dict]:
        """미리 추출된 데이터 활용"""
        chunks = []
        
        # extern 청크
        if extern_region.get("code"):
            extern_elements = extern_region.get("elements", {})
            all_extern_elements = []
            
            for category, items in extern_elements.items():
                if isinstance(items, list):
                    for item in items:
                        all_extern_elements.append({**item, "category": category})
            
            chunks.append({
                "scope": "extern",
                "code": extern_region["code"],
                "elements": all_extern_elements,
                "line_ranges": extern_region.get("line_ranges", [])
            })
        
        # 함수별 청크
        lines = source_code.split("\n")
        for func in parsed_functions:
            start_idx = max(0, func["line_start"] - 1)
            end_idx = min(len(lines), func["line_end"])
            func_code = "\n".join(lines[start_idx:end_idx])
            func_elements = self._get_elements_in_range(
                metadata, func["line_start"], func["line_end"]
            )
            
            chunks.append({
                "scope": f"function_{func['name']}",
                "code": func_code,
                "elements": func_elements,
                "line_range": (func["line_start"], func["line_end"])
            })
        
        logger.info(f"캐시 활용: extern + {len(parsed_functions)}개 함수")
        return chunks
    
    def _split_with_tree_sitter(
        self, 
        source_code: str, 
        metadata: Dict
    ) -> List[Dict]:
        """tree-sitter 사용하여 분할"""
        extractor = self._get_extractor()
        if not extractor:
            return []
        
        chunks = []
        
        # extern 영역 추출
        extern_data = extractor.get_extern_region(source_code)
        functions = extractor.get_functions(source_code)
        
        # extern 청크
        if extern_data.get("code"):
            extern_elements = extern_data.get("elements", {})
            all_extern_elements = []
            
            for category, items in extern_elements.items():
                if isinstance(items, list):
                    for item in items:
                        all_extern_elements.append({**item, "category": category})
            
            chunks.append({
                "scope": "extern",
                "code": extern_data["code"],
                "elements": all_extern_elements,
                "line_ranges": extern_data.get("line_ranges", [])
            })
        
        # 함수별 청크
        lines = source_code.split("\n")
        for func in functions:
            start_idx = max(0, func["line_start"] - 1)
            end_idx = min(len(lines), func["line_end"])
            func_code = "\n".join(lines[start_idx:end_idx])
            func_elements = self._get_elements_in_range(
                metadata, func["line_start"], func["line_end"]
            )
            
            chunks.append({
                "scope": f"function_{func['name']}",
                "code": func_code,
                "elements": func_elements,
                "line_range": (func["line_start"], func["line_end"])
            })
        
        logger.info(f"tree-sitter: extern + {len(functions)}개 함수")
        return chunks
    
    def _split_fallback(self, source_code: str, metadata: Dict) -> List[Dict]:
        """tree-sitter 없을 때 폴백 분할"""
        chunks = []
        functions = metadata.get("functions", [])
        lines = source_code.split("\n")
        
        # 함수 위치 수집
        func_ranges = []
        covered_lines = set()
        
        for func in functions:
            start = func.get("line_start", 0)
            end = func.get("line_end", start + self.DEFAULT_FUNC_LINE_RANGE)
            func_ranges.append({
                "name": func.get("name", "unknown"), 
                "start": start, 
                "end": end
            })
            for i in range(start - 1, min(end, len(lines))):
                covered_lines.add(i)
        
        # extern 영역 (함수 밖의 라인들)
        extern_lines = [
            (i + 1, line) for i, line in enumerate(lines) 
            if i not in covered_lines
        ]
        
        if extern_lines:
            extern_code = "\n".join([line for _, line in extern_lines])
            max_line = max(i for i, _ in extern_lines) + 1
            extern_elements = self._get_elements_in_range(metadata, 0, max_line)
            
            chunks.append({
                "scope": "extern",
                "code": extern_code,
                "elements": extern_elements,
                "line_range": (1, max_line)
            })
        
        # 함수별 청크
        for fr in func_ranges:
            start_idx = max(0, fr["start"] - 1)
            end_idx = min(len(lines), fr["end"])
            func_code = "\n".join(lines[start_idx:end_idx])
            func_elements = self._get_elements_in_range(
                metadata, fr["start"], fr["end"]
            )
            
            chunks.append({
                "scope": f"function_{fr['name']}",
                "code": func_code,
                "elements": func_elements,
                "line_range": (fr["start"], fr["end"])
            })
        
        logger.info(f"폴백 분할: extern + {len(func_ranges)}개 함수")
        return chunks
    
    def _get_elements_in_range(
        self, 
        metadata: Dict, 
        start: int, 
        end: int
    ) -> List[Dict]:
        """특정 라인 범위 내의 요소들 수집"""
        elements = []
        
        for category, items in metadata.items():
            if isinstance(items, list):
                for item in items:
                    item_start = item.get("line_start", 0)
                    item_end = item.get("line_end", item_start)
                    
                    if start <= item_start <= end or start <= item_end <= end:
                        elements.append({**item, "category": category})
        
        return elements
