"""
파일 시스템 관련 도구들
"""
import os
import re
import glob as glob_module
from pathlib import Path
from typing import Optional

from .base import ToolDefinition


def _read_file(
    file_path: str,
    start_line: int = None,
    end_line: int = None
) -> str:
    """
    파일 내용 읽기
    
    Args:
        file_path: 읽을 파일 경로
        start_line: 시작 줄 번호 (1-indexed, 선택)
        end_line: 종료 줄 번호 (1-indexed, 선택)
    
    Returns:
        파일 내용 또는 지정된 줄 범위
    """
    path = Path(file_path)
    if not path.exists():
        return f"Error: 파일을 찾을 수 없습니다: {file_path}"
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        if start_line is not None or end_line is not None:
            start_idx = (start_line - 1) if start_line else 0
            end_idx = end_line if end_line else len(lines)
            lines = lines[start_idx:end_idx]
        
        return "".join(lines)
    except Exception as e:
        return f"Error: 파일 읽기 실패: {e}"


def _write_file(
    file_path: str,
    content: str,
    create_dirs: bool = True
) -> str:
    """
    파일에 내용 쓰기
    
    Args:
        file_path: 쓸 파일 경로
        content: 파일 내용
        create_dirs: 부모 디렉토리 자동 생성 여부
    
    Returns:
        성공/실패 메시지
    """
    path = Path(file_path)
    
    try:
        if create_dirs:
            path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        
        return f"Success: 파일 저장됨: {file_path}"
    except Exception as e:
        return f"Error: 파일 쓰기 실패: {e}"


def _glob_search(
    pattern: str,
    directory: str = ".",
    recursive: bool = True
) -> str:
    """
    Glob 패턴으로 파일 검색
    
    Args:
        pattern: glob 패턴 (예: "*.py", "**/*.pc")
        directory: 검색 시작 디렉토리
        recursive: 재귀 검색 여부
    
    Returns:
        매칭된 파일 목록 (줄바꿈 구분)
    """
    try:
        base_path = Path(directory)
        
        if recursive and "**" not in pattern:
            pattern = f"**/{pattern}"
        
        matches = list(base_path.glob(pattern))
        
        if not matches:
            return f"No files found matching: {pattern}"
        
        # 최대 50개로 제한
        if len(matches) > 50:
            matches = matches[:50]
            result = "\n".join(str(m) for m in matches)
            return f"{result}\n... (50개 이상, 결과 제한됨)"
        
        return "\n".join(str(m) for m in matches)
    except Exception as e:
        return f"Error: 검색 실패: {e}"


def _grep_search(
    pattern: str,
    file_path: str = None,
    directory: str = None,
    file_pattern: str = "*",
    case_insensitive: bool = True
) -> str:
    """
    정규식 패턴으로 파일 내용 검색
    
    Args:
        pattern: 검색 정규식 패턴
        file_path: 검색할 단일 파일 (directory와 배타적)
        directory: 검색할 디렉토리 (file_path와 배타적)
        file_pattern: 디렉토리 검색 시 파일 패턴
        case_insensitive: 대소문자 무시 여부
    
    Returns:
        매칭된 줄 목록 (파일명:줄번호:내용)
    """
    try:
        flags = re.IGNORECASE if case_insensitive else 0
        regex = re.compile(pattern, flags)
        results = []
        
        if file_path:
            files = [Path(file_path)]
        elif directory:
            files = list(Path(directory).rglob(file_pattern))
        else:
            return "Error: file_path 또는 directory를 지정해야 합니다."
        
        for fp in files[:100]:  # 최대 100개 파일
            if not fp.is_file():
                continue
            
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    for i, line in enumerate(f, 1):
                        if regex.search(line):
                            results.append(f"{fp}:{i}:{line.rstrip()}")
                            if len(results) >= 50:
                                break
            except Exception:
                continue
            
            if len(results) >= 50:
                break
        
        if not results:
            return f"No matches found for: {pattern}"
        
        return "\n".join(results)
    except Exception as e:
        return f"Error: 검색 실패: {e}"


def _list_dir(
    directory: str = ".",
    show_hidden: bool = False
) -> str:
    """
    디렉토리 내용 목록
    
    Args:
        directory: 목록을 볼 디렉토리
        show_hidden: 숨김 파일 표시 여부
    
    Returns:
        디렉토리 내용 목록
    """
    try:
        path = Path(directory)
        if not path.exists():
            return f"Error: 디렉토리를 찾을 수 없습니다: {directory}"
        
        items = []
        for item in sorted(path.iterdir()):
            name = item.name
            if not show_hidden and name.startswith("."):
                continue
            
            if item.is_dir():
                items.append(f"[DIR]  {name}/")
            else:
                size = item.stat().st_size
                items.append(f"[FILE] {name} ({size} bytes)")
        
        if not items:
            return f"Empty directory: {directory}"
        
        return "\n".join(items)
    except Exception as e:
        return f"Error: 목록 조회 실패: {e}"


# 도구 정의들
read_file_tool = ToolDefinition(
    name="read_file",
    description="파일 내용을 읽습니다. 줄 범위를 지정할 수 있습니다.",
    func=_read_file,
    parameters={
        "file_path": {"type": "string", "description": "읽을 파일 경로", "required": True},
        "start_line": {"type": "integer", "description": "시작 줄 번호 (1-indexed)"},
        "end_line": {"type": "integer", "description": "종료 줄 번호 (1-indexed)"},
    }
)

write_file_tool = ToolDefinition(
    name="write_file",
    description="파일에 내용을 씁니다. 부모 디렉토리가 없으면 생성합니다.",
    func=_write_file,
    parameters={
        "file_path": {"type": "string", "description": "쓸 파일 경로", "required": True},
        "content": {"type": "string", "description": "파일 내용", "required": True},
        "create_dirs": {"type": "boolean", "description": "디렉토리 자동 생성", "default": True},
    }
)

glob_tool = ToolDefinition(
    name="glob_search",
    description="Glob 패턴으로 파일을 검색합니다. 예: *.py, **/*.pc",
    func=_glob_search,
    parameters={
        "pattern": {"type": "string", "description": "glob 패턴", "required": True},
        "directory": {"type": "string", "description": "검색 시작 디렉토리", "default": "."},
        "recursive": {"type": "boolean", "description": "재귀 검색", "default": True},
    }
)

grep_tool = ToolDefinition(
    name="grep_search",
    description="정규식 패턴으로 파일 내용을 검색합니다.",
    func=_grep_search,
    parameters={
        "pattern": {"type": "string", "description": "검색 정규식", "required": True},
        "file_path": {"type": "string", "description": "검색할 파일"},
        "directory": {"type": "string", "description": "검색할 디렉토리"},
        "file_pattern": {"type": "string", "description": "파일 패턴", "default": "*"},
        "case_insensitive": {"type": "boolean", "description": "대소문자 무시", "default": True},
    }
)

list_dir_tool = ToolDefinition(
    name="list_dir",
    description="디렉토리 내용을 목록으로 보여줍니다.",
    func=_list_dir,
    parameters={
        "directory": {"type": "string", "description": "디렉토리 경로", "default": "."},
        "show_hidden": {"type": "boolean", "description": "숨김 파일 표시", "default": False},
    }
)
