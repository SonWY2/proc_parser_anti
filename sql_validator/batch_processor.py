"""
일괄 처리 모듈

여러 YAML 파일을 일괄로 검증하고 리포트를 생성합니다.
"""

from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger

from .yaml_loader import load_yaml
from .static_analyzer import StaticAnalyzer, AnalysisResult
from .diff_highlighter import DiffHighlighter


@dataclass
class FileResult:
    """개별 파일 처리 결과"""
    file_path: str
    item_count: int
    pass_count: int
    fail_count: int
    warning_count: int
    error: Optional[str] = None
    items: List[Dict[str, Any]] = field(default_factory=list)
    analysis_results: List[AnalysisResult] = field(default_factory=list)


@dataclass
class BatchResult:
    """일괄 처리 결과"""
    file_results: List[FileResult] = field(default_factory=list)
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    @property
    def total_files(self) -> int:
        return len(self.file_results)
    
    @property
    def successful_files(self) -> int:
        return sum(1 for r in self.file_results if r.error is None)
    
    @property
    def total_items(self) -> int:
        return sum(r.item_count for r in self.file_results)
    
    @property
    def total_pass(self) -> int:
        return sum(r.pass_count for r in self.file_results)
    
    @property
    def total_fail(self) -> int:
        return sum(r.fail_count for r in self.file_results)
    
    @property
    def total_warning(self) -> int:
        return sum(r.warning_count for r in self.file_results)


def process_file(yaml_path: str, analyzer: StaticAnalyzer) -> FileResult:
    """
    단일 YAML 파일을 처리합니다.
    
    Args:
        yaml_path: YAML 파일 경로
        analyzer: StaticAnalyzer 인스턴스
        
    Returns:
        FileResult 객체
    """
    try:
        items = load_yaml(yaml_path)
        
        if not items:
            return FileResult(
                file_path=yaml_path,
                item_count=0,
                pass_count=0,
                fail_count=0,
                warning_count=0,
                error="유효한 SQL 항목이 없습니다"
            )
        
        analysis_results = []
        total_pass = 0
        total_fail = 0
        total_warning = 0
        
        for item in items:
            result = analyzer.analyze(item['sql'], item['parsed_sql'])
            analysis_results.append(result)
            total_pass += result.pass_count
            total_fail += result.fail_count
            total_warning += result.warning_count
        
        return FileResult(
            file_path=yaml_path,
            item_count=len(items),
            pass_count=total_pass,
            fail_count=total_fail,
            warning_count=total_warning,
            items=items,
            analysis_results=analysis_results
        )
        
    except Exception as e:
        logger.error(f"파일 처리 실패: {yaml_path} - {e}")
        return FileResult(
            file_path=yaml_path,
            item_count=0,
            pass_count=0,
            fail_count=0,
            warning_count=0,
            error=str(e)
        )


def process_batch(yaml_paths: List[str]) -> BatchResult:
    """
    여러 YAML 파일을 일괄 처리합니다.
    
    Args:
        yaml_paths: YAML 파일 경로 리스트
        
    Returns:
        BatchResult 객체
    """
    analyzer = StaticAnalyzer()
    results = []
    
    for path in yaml_paths:
        logger.info(f"처리 중: {path}")
        result = process_file(path, analyzer)
        results.append(result)
    
    return BatchResult(file_results=results)


def generate_markdown_report(result: BatchResult) -> str:
    """
    Markdown 형식의 리포트를 생성합니다.
    
    Args:
        result: BatchResult 객체
        
    Returns:
        Markdown 문자열
    """
    lines = [
        "# SQL 변환 검증 리포트",
        "",
        f"생성 시각: {result.timestamp}",
        "",
        "## 요약",
        "",
        f"- 처리된 파일: {result.total_files}개",
        f"- 성공한 파일: {result.successful_files}개",
        f"- 총 SQL 항목: {result.total_items}개",
        f"- 총 통과: {result.total_pass}",
        f"- 총 실패: {result.total_fail}",
        f"- 총 경고: {result.total_warning}",
        "",
        "## 파일별 결과",
        ""
    ]
    
    for fr in result.file_results:
        file_name = Path(fr.file_path).name
        
        if fr.error:
            lines.append(f"### ❌ {file_name}")
            lines.append(f"오류: {fr.error}")
        else:
            status_icon = "✅" if fr.fail_count == 0 else "⚠️"
            lines.append(f"### {status_icon} {file_name}")
            lines.append(f"- 항목 수: {fr.item_count}")
            lines.append(f"- 통과: {fr.pass_count}, 실패: {fr.fail_count}, 경고: {fr.warning_count}")
        
        lines.append("")
    
    return '\n'.join(lines)


def generate_html_report(result: BatchResult) -> str:
    """
    HTML 형식의 리포트를 생성합니다.
    
    Args:
        result: BatchResult 객체
        
    Returns:
        HTML 문자열
    """
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>SQL 변환 검증 리포트</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .summary {{ background: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        .file-result {{ border: 1px solid #ddd; padding: 15px; margin-bottom: 10px; border-radius: 5px; }}
        .success {{ border-left: 4px solid #28a745; }}
        .warning {{ border-left: 4px solid #ffc107; }}
        .error {{ border-left: 4px solid #dc3545; }}
        .stats {{ display: flex; gap: 20px; }}
        .stat {{ text-align: center; }}
        .stat-value {{ font-size: 24px; font-weight: bold; }}
        .pass {{ color: #28a745; }}
        .fail {{ color: #dc3545; }}
        .warn {{ color: #ffc107; }}
    </style>
</head>
<body>
    <h1>SQL 변환 검증 리포트</h1>
    <p>생성 시각: {result.timestamp}</p>
    
    <div class="summary">
        <h2>요약</h2>
        <div class="stats">
            <div class="stat">
                <div class="stat-value">{result.total_files}</div>
                <div>처리된 파일</div>
            </div>
            <div class="stat">
                <div class="stat-value">{result.total_items}</div>
                <div>총 SQL 항목</div>
            </div>
            <div class="stat">
                <div class="stat-value pass">{result.total_pass}</div>
                <div>통과</div>
            </div>
            <div class="stat">
                <div class="stat-value fail">{result.total_fail}</div>
                <div>실패</div>
            </div>
            <div class="stat">
                <div class="stat-value warn">{result.total_warning}</div>
                <div>경고</div>
            </div>
        </div>
    </div>
    
    <h2>파일별 결과</h2>
"""
    
    for fr in result.file_results:
        file_name = Path(fr.file_path).name
        
        if fr.error:
            css_class = "error"
            status = "❌ 오류"
            content = f"<p>오류: {fr.error}</p>"
        elif fr.fail_count > 0:
            css_class = "warning"
            status = "⚠️ 경고"
            content = f"<p>항목: {fr.item_count} | 통과: {fr.pass_count} | 실패: {fr.fail_count} | 경고: {fr.warning_count}</p>"
        else:
            css_class = "success"
            status = "✅ 성공"
            content = f"<p>항목: {fr.item_count} | 통과: {fr.pass_count} | 경고: {fr.warning_count}</p>"
        
        html += f"""
    <div class="file-result {css_class}">
        <h3>{status} {file_name}</h3>
        {content}
    </div>
"""
    
    html += """
</body>
</html>
"""
    
    return html


def save_report(result: BatchResult, output_path: str, format: str = 'markdown') -> bool:
    """
    리포트를 파일로 저장합니다.
    
    Args:
        result: BatchResult 객체
        output_path: 출력 파일 경로
        format: 'markdown' 또는 'html'
        
    Returns:
        성공 여부
    """
    try:
        if format == 'html':
            content = generate_html_report(result)
        else:
            content = generate_markdown_report(result)
        
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"리포트 저장됨: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"리포트 저장 실패: {e}")
        return False
