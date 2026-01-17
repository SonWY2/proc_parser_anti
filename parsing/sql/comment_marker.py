"""
SQL 주석 마커 모듈

추출된 SQL 위치에 주석을 삽입하는 기능을 제공합니다.
주석 포맷은 커스터마이징 가능합니다.
"""

from typing import Callable, Optional


# ============================================================================
# 기본 주석 포맷터 함수들 (커스터마이징 가능)
# ============================================================================

def default_comment_formatter(sql_id: str, sql_type: str, **kwargs) -> str:
    """
    기본 주석 포맷터
    
    Args:
        sql_id: SQL ID (예: select_0)
        sql_type: SQL 타입 (예: select)
        **kwargs: 추가 메타데이터
    
    Returns:
        주석 문자열
    """
    return f"/* sql extracted: {sql_id} */"


def detailed_comment_formatter(sql_id: str, sql_type: str, **kwargs) -> str:
    """
    상세 정보를 포함하는 주석 포맷터
    
    Args:
        sql_id: SQL ID
        sql_type: SQL 타입
        **kwargs: 추가 메타데이터 (function_name, line_start 등)
    
    Returns:
        상세 주석 문자열
    """
    func_name = kwargs.get('function_name', 'unknown')
    line = kwargs.get('line_start', 0)
    return f"/* sql extracted: {sql_id} | type: {sql_type} | func: {func_name} | line: {line} */"


def mybatis_ref_comment_formatter(sql_id: str, sql_type: str, **kwargs) -> str:
    """
    MyBatis 참조 스타일 주석 포맷터
    
    Args:
        sql_id: SQL ID
        sql_type: SQL 타입
    
    Returns:
        MyBatis 참조 스타일 주석
    """
    return f"/* @mybatis:{sql_id} ({sql_type}) */"


def c_style_marker_formatter(sql_id: str, sql_type: str, **kwargs) -> str:
    """
    C 스타일 마커 주석 포맷터 (원본 코드 호환용)
    
    Args:
        sql_id: SQL ID
        sql_type: SQL 타입
    
    Returns:
        C 스타일 주석
    """
    return f"// SQL_MARKER: {sql_id}"


class SQLCommentMarker:
    """
    SQL 추출 위치에 주석을 삽입하는 마커
    
    Example:
        marker = SQLCommentMarker()
        comment = marker.mark("select_0", "select")
        # 결과: /* sql extracted: select_0 */
        
        # 커스텀 포맷터 사용
        marker = SQLCommentMarker(formatter=detailed_comment_formatter)
        comment = marker.mark("select_0", "select", function_name="get_user", line_start=42)
        # 결과: /* sql extracted: select_0 | type: select | func: get_user | line: 42 */
    """
    
    def __init__(
        self,
        formatter: Callable[..., str] = None,
        format_template: str = None
    ):
        """
        마커 초기화
        
        Args:
            formatter: 주석 생성 함수. (sql_id, sql_type, **kwargs) -> str
                       지정하지 않으면 기본 포맷터 사용
            format_template: 간단한 템플릿 문자열 (formatter 대신 사용 가능)
                             예: "/* sql: {sql_id} - {sql_type} */"
        """
        if formatter:
            self._formatter = formatter
        elif format_template:
            self._formatter = self._create_template_formatter(format_template)
        else:
            self._formatter = default_comment_formatter
    
    def mark(self, sql_id: str, sql_type: str, **kwargs) -> str:
        """
        SQL에 대한 주석 생성
        
        Args:
            sql_id: SQL ID (예: select_0)
            sql_type: SQL 타입 (예: select)
            **kwargs: 추가 메타데이터 (function_name, line_start 등)
        
        Returns:
            주석 문자열
        """
        return self._formatter(sql_id, sql_type, **kwargs)
    
    def mark_with_call(
        self, 
        sql_id: str, 
        sql_name: str, 
        call_format: str = 'sql_call("{sql_id}", "{sql_name}");'
    ) -> str:
        """
        SQL 호출문과 주석을 함께 생성
        
        Args:
            sql_id: SQL ID
            sql_name: SQL 이름
            call_format: 호출문 포맷 (기본: sql_call("id", "name");)
        
        Returns:
            주석 + 호출문 문자열
        """
        comment = self.mark(sql_id, sql_name)
        call = call_format.format(sql_id=sql_id, sql_name=sql_name)
        return f"{comment}\n{call}"
    
    def set_formatter(self, formatter: Callable[..., str]):
        """포맷터 변경"""
        self._formatter = formatter
    
    def set_template(self, template: str):
        """템플릿 문자열로 포맷터 설정"""
        self._formatter = self._create_template_formatter(template)
    
    def _create_template_formatter(self, template: str) -> Callable[..., str]:
        """템플릿 문자열로부터 포맷터 함수 생성"""
        def template_formatter(sql_id: str, sql_type: str, **kwargs) -> str:
            return template.format(sql_id=sql_id, sql_type=sql_type, **kwargs)
        return template_formatter


# 편의 함수
def create_marker(
    style: str = "default",
    custom_template: str = None
) -> SQLCommentMarker:
    """
    주석 마커 생성 편의 함수
    
    Args:
        style: 스타일 선택 ("default", "detailed", "mybatis", "c_style")
        custom_template: 커스텀 템플릿 (style 무시)
    
    Returns:
        SQLCommentMarker 인스턴스
    """
    if custom_template:
        return SQLCommentMarker(format_template=custom_template)
    
    formatters = {
        "default": default_comment_formatter,
        "detailed": detailed_comment_formatter,
        "mybatis": mybatis_ref_comment_formatter,
        "c_style": c_style_marker_formatter,
    }
    
    formatter = formatters.get(style, default_comment_formatter)
    return SQLCommentMarker(formatter=formatter)
