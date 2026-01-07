"""
SQL 카운터 전용 도구

Pro*C 코드에서 SQL 구문을 추출하고 개수를 세는 도구들입니다.
"""

import re
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# 상위 모듈에서 Tool, ToolResult 가져오기
from .tools import Tool, ToolResult


class ChunkCodeTool(Tool):
    """코드 청킹 도구
    
    긴 코드를 SQL 구문이 잘리지 않도록 일정 길이의 청크로 분할합니다.
    """
    
    name = "ChunkCode"
    description = "긴 코드를 SQL 구문 경계를 고려하여 청크로 분할합니다."
    is_readonly = True
    
    # EXEC SQL 패턴 (여러 줄에 걸친 구문도 고려)
    EXEC_SQL_PATTERN = re.compile(
        r'EXEC\s+SQL\s+.*?;',
        re.DOTALL | re.IGNORECASE
    )
    
    def execute(
        self, 
        code: str, 
        chunk_size: int = 5000,
        overlap: int = 100
    ) -> ToolResult:
        """
        Args:
            code: 분할할 코드
            chunk_size: 청크 크기 (기본값: 5000자)
            overlap: 청크 간 중복 영역 (기본값: 100자)
        """
        try:
            total_length = len(code)
            
            # 짧은 코드는 분할 불필요
            if total_length <= chunk_size:
                result = {
                    "total_length": total_length,
                    "chunk_count": 1,
                    "chunks": [{
                        "index": 0,
                        "content": code,
                        "start": 0,
                        "end": total_length
                    }]
                }
                return ToolResult(True, json.dumps(result, ensure_ascii=False, indent=2))
            
            chunks = []
            pos = 0
            chunk_index = 0
            
            while pos < total_length:
                # 기본 청크 끝 위치
                end_pos = min(pos + chunk_size, total_length)
                
                # 마지막 청크가 아닌 경우, SQL 구문이 잘리지 않도록 조정
                if end_pos < total_length:
                    # end_pos 근처에서 EXEC SQL 시작점 찾기
                    search_start = max(0, end_pos - 500)
                    search_region = code[search_start:end_pos + 500]
                    
                    # 세미콜론 뒤 또는 줄바꿈을 찾아 청크 경계로 사용
                    # EXEC SQL 구문 내부가 아닌 위치 찾기
                    adjusted_end = self._find_safe_boundary(code, end_pos)
                    if adjusted_end > pos:
                        end_pos = adjusted_end
                
                chunk_content = code[pos:end_pos]
                chunks.append({
                    "index": chunk_index,
                    "content": chunk_content,
                    "start": pos,
                    "end": end_pos
                })
                
                # 다음 청크 시작 위치 (overlap 적용)
                pos = end_pos - overlap if end_pos < total_length else total_length
                chunk_index += 1
            
            result = {
                "total_length": total_length,
                "chunk_count": len(chunks),
                "chunks": chunks
            }
            
            return ToolResult(True, json.dumps(result, ensure_ascii=False, indent=2))
            
        except Exception as e:
            return ToolResult(False, "", str(e))
    
    def _find_safe_boundary(self, code: str, target_pos: int) -> int:
        """SQL 구문이 잘리지 않는 안전한 경계 찾기"""
        # target_pos 근처에서 세미콜론+줄바꿈 찾기
        search_range = 500
        start = max(0, target_pos - search_range)
        end = min(len(code), target_pos + search_range)
        
        region = code[start:end]
        
        # 세미콜론 뒤 줄바꿈을 찾아 가장 target_pos에 가까운 것 선택
        best_pos = target_pos
        best_diff = float('inf')
        
        for match in re.finditer(r';\s*\n', region):
            abs_pos = start + match.end()
            diff = abs(abs_pos - target_pos)
            if diff < best_diff:
                best_diff = diff
                best_pos = abs_pos
        
        return best_pos
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "분할할 코드"},
                "chunk_size": {"type": "integer", "description": "청크 크기 (기본값: 5000)", "default": 5000},
                "overlap": {"type": "integer", "description": "청크 간 중복 영역 (기본값: 100)", "default": 100}
            },
            "required": ["code"]
        }


class CountSQLTool(Tool):
    """SQL 구문 카운팅 도구
    
    Pro*C 코드에서 EXEC SQL 구문을 찾아 타입별로 분류하고 개수를 셉니다.
    """
    
    name = "CountSQL"
    description = "Pro*C 코드에서 SQL 구문 개수를 추출하고 타입별로 분류합니다."
    is_readonly = True
    
    # SQL 타입 패턴 정의
    SQL_TYPE_PATTERNS = [
        ("SELECT", re.compile(r'EXEC\s+SQL\s+SELECT\b', re.IGNORECASE)),
        ("INSERT", re.compile(r'EXEC\s+SQL\s+INSERT\b', re.IGNORECASE)),
        ("UPDATE", re.compile(r'EXEC\s+SQL\s+UPDATE\b', re.IGNORECASE)),
        ("DELETE", re.compile(r'EXEC\s+SQL\s+DELETE\b', re.IGNORECASE)),
        ("CURSOR", re.compile(r'EXEC\s+SQL\s+DECLARE\s+\w+\s+CURSOR\b', re.IGNORECASE)),
        ("FETCH", re.compile(r'EXEC\s+SQL\s+FETCH\b', re.IGNORECASE)),
        ("OPEN", re.compile(r'EXEC\s+SQL\s+OPEN\b', re.IGNORECASE)),
        ("CLOSE", re.compile(r'EXEC\s+SQL\s+CLOSE\b', re.IGNORECASE)),
        ("PREPARE", re.compile(r'EXEC\s+SQL\s+PREPARE\b', re.IGNORECASE)),
        ("EXECUTE", re.compile(r'EXEC\s+SQL\s+EXECUTE\b', re.IGNORECASE)),
        ("INCLUDE", re.compile(r'EXEC\s+SQL\s+INCLUDE\b', re.IGNORECASE)),
        ("BEGIN_DECLARE", re.compile(r'EXEC\s+SQL\s+BEGIN\s+DECLARE\s+SECTION', re.IGNORECASE)),
        ("END_DECLARE", re.compile(r'EXEC\s+SQL\s+END\s+DECLARE\s+SECTION', re.IGNORECASE)),
        ("CONNECT", re.compile(r'EXEC\s+SQL\s+CONNECT\b', re.IGNORECASE)),
        ("COMMIT", re.compile(r'EXEC\s+SQL\s+COMMIT\b', re.IGNORECASE)),
        ("ROLLBACK", re.compile(r'EXEC\s+SQL\s+ROLLBACK\b', re.IGNORECASE)),
        ("WHENEVER", re.compile(r'EXEC\s+SQL\s+WHENEVER\b', re.IGNORECASE)),
        ("CALL", re.compile(r'EXEC\s+SQL\s+CALL\b', re.IGNORECASE)),
    ]
    
    # 주석 패턴
    BLOCK_COMMENT = re.compile(r'/\*.*?\*/', re.DOTALL)
    LINE_COMMENT = re.compile(r'//.*?$|--.*?$', re.MULTILINE)
    
    # EXEC SQL 전체 패턴
    EXEC_SQL_PATTERN = re.compile(
        r'EXEC\s+SQL\s+.*?;',
        re.DOTALL | re.IGNORECASE
    )
    
    def execute(
        self, 
        code: str,
        chunk_index: int = 0,
        include_details: bool = False
    ) -> ToolResult:
        """
        Args:
            code: 분석할 코드
            chunk_index: 청크 인덱스 (결과에 포함)
            include_details: 상세 정보 포함 여부
        """
        try:
            # 주석 제거
            code_no_comments = self._remove_comments(code)
            
            # SQL 타입별 카운트
            by_type = {}
            details = []
            
            for sql_type, pattern in self.SQL_TYPE_PATTERNS:
                matches = list(pattern.finditer(code_no_comments))
                if matches:
                    by_type[sql_type] = len(matches)
                    
                    if include_details:
                        for match in matches:
                            # 해당 위치의 라인 번호 계산
                            line_num = code_no_comments[:match.start()].count('\n') + 1
                            # SQL 구문 추출 (최대 100자)
                            snippet = self._extract_sql_snippet(code_no_comments, match.start())
                            details.append({
                                "line": line_num,
                                "type": sql_type,
                                "snippet": snippet
                            })
            
            total = sum(by_type.values())
            
            result = {
                "chunk_index": chunk_index,
                "sql_count": {
                    "total": total,
                    "by_type": by_type
                }
            }
            
            if include_details:
                result["details"] = sorted(details, key=lambda x: x["line"])
            
            return ToolResult(True, json.dumps(result, ensure_ascii=False, indent=2))
            
        except Exception as e:
            return ToolResult(False, "", str(e))
    
    def _remove_comments(self, code: str) -> str:
        """주석 제거"""
        # 블록 주석 제거
        code = self.BLOCK_COMMENT.sub('', code)
        # 라인 주석 제거
        code = self.LINE_COMMENT.sub('', code)
        return code
    
    def _extract_sql_snippet(self, code: str, start_pos: int, max_length: int = 100) -> str:
        """SQL 구문 스니펫 추출"""
        # 세미콜론까지 또는 max_length까지
        end_pos = code.find(';', start_pos)
        if end_pos == -1:
            end_pos = start_pos + max_length
        else:
            end_pos = min(end_pos + 1, start_pos + max_length)
        
        snippet = code[start_pos:end_pos].strip()
        snippet = re.sub(r'\s+', ' ', snippet)  # 연속 공백 정리
        
        if end_pos - start_pos >= max_length:
            snippet += "..."
        
        return snippet
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "분석할 Pro*C 코드"},
                "chunk_index": {"type": "integer", "description": "청크 인덱스", "default": 0},
                "include_details": {"type": "boolean", "description": "상세 정보 포함 여부", "default": False}
            },
            "required": ["code"]
        }


class AggregateResultsTool(Tool):
    """결과 통합 도구
    
    여러 청크의 SQL 카운팅 결과를 통합합니다.
    """
    
    name = "AggregateResults"
    description = "여러 청크의 SQL 카운팅 결과를 통합하여 최종 통계를 생성합니다."
    is_readonly = True
    
    def execute(
        self, 
        results: str,
        remove_duplicates: bool = False
    ) -> ToolResult:
        """
        Args:
            results: 청크별 결과 JSON 배열 (문자열)
            remove_duplicates: 중복 제거 여부 (청크 경계 중복)
        """
        try:
            # JSON 파싱
            if isinstance(results, str):
                result_list = json.loads(results)
            else:
                result_list = results
            
            # 타입별 합계
            total_by_type = {}
            total_count = 0
            per_chunk = []
            
            for item in result_list:
                chunk_index = item.get("chunk_index", 0)
                sql_count = item.get("sql_count", {})
                chunk_total = sql_count.get("total", 0)
                by_type = sql_count.get("by_type", {})
                
                total_count += chunk_total
                per_chunk.append({
                    "index": chunk_index,
                    "count": chunk_total
                })
                
                for sql_type, count in by_type.items():
                    total_by_type[sql_type] = total_by_type.get(sql_type, 0) + count
            
            result = {
                "status": "success",
                "summary": {
                    "total_sql_count": total_count,
                    "by_type": total_by_type,
                    "chunks_processed": len(result_list)
                },
                "per_chunk": sorted(per_chunk, key=lambda x: x["index"])
            }
            
            return ToolResult(True, json.dumps(result, ensure_ascii=False, indent=2))
            
        except json.JSONDecodeError as e:
            return ToolResult(False, "", f"JSON 파싱 오류: {e}")
        except Exception as e:
            return ToolResult(False, "", str(e))
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "results": {"type": "string", "description": "청크별 결과 JSON 배열"},
                "remove_duplicates": {"type": "boolean", "description": "중복 제거 여부", "default": False}
            },
            "required": ["results"]
        }


def register_sql_counter_tools(registry):
    """SQL 카운터 도구들을 레지스트리에 등록
    
    Args:
        registry: ToolRegistry 인스턴스
    """
    registry.register(ChunkCodeTool())
    registry.register(CountSQLTool())
    registry.register(AggregateResultsTool())


# 편의를 위한 직접 사용 가능한 인스턴스
chunk_code_tool = ChunkCodeTool()
count_sql_tool = CountSQLTool()
aggregate_results_tool = AggregateResultsTool()
