"""
도구 시스템

서브에이전트가 사용할 수 있는 도구들을 정의합니다.
"""

import subprocess
import glob as glob_module
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Any, Optional


@dataclass
class ToolResult:
    """도구 실행 결과"""
    success: bool
    output: str
    error: Optional[str] = None


class Tool(ABC):
    """도구 기본 클래스"""
    
    name: str = ""
    description: str = ""
    is_readonly: bool = True
    
    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """도구 실행"""
        pass
    
    def get_schema(self) -> Dict[str, Any]:
        """도구 스키마 반환 (LLM function calling용)"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self._get_parameters()
        }
    
    @abstractmethod
    def _get_parameters(self) -> Dict[str, Any]:
        """파라미터 스키마 반환"""
        pass


class ReadTool(Tool):
    """파일 읽기 도구"""
    
    name = "Read"
    description = "파일 내용을 읽습니다."
    is_readonly = True
    
    def execute(self, file_path: str, start_line: int = 1, end_line: int = -1) -> ToolResult:
        """
        Args:
            file_path: 읽을 파일 경로
            start_line: 시작 줄 번호 (1부터)
            end_line: 끝 줄 번호 (-1이면 끝까지)
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return ToolResult(False, "", f"파일이 존재하지 않습니다: {file_path}")
            
            content = path.read_text(encoding='utf-8')
            lines = content.splitlines()
            
            # 줄 범위 적용
            start_idx = max(0, start_line - 1)
            end_idx = len(lines) if end_line == -1 else min(end_line, len(lines))
            
            selected_lines = lines[start_idx:end_idx]
            output = '\n'.join(f"{i+start_line}: {line}" for i, line in enumerate(selected_lines))
            
            return ToolResult(True, output)
        except Exception as e:
            return ToolResult(False, "", str(e))
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "읽을 파일 경로"},
                "start_line": {"type": "integer", "description": "시작 줄 번호 (1부터)", "default": 1},
                "end_line": {"type": "integer", "description": "끝 줄 번호 (-1이면 끝까지)", "default": -1}
            },
            "required": ["file_path"]
        }


class GrepTool(Tool):
    """패턴 검색 도구"""
    
    name = "Grep"
    description = "파일에서 패턴을 검색합니다."
    is_readonly = True
    
    def execute(self, pattern: str, path: str, recursive: bool = True, 
                case_insensitive: bool = False) -> ToolResult:
        """
        Args:
            pattern: 검색할 정규식 패턴
            path: 검색할 파일 또는 디렉토리 경로
            recursive: 하위 디렉토리 포함 여부
            case_insensitive: 대소문자 무시 여부
        """
        try:
            target_path = Path(path)
            flags = re.IGNORECASE if case_insensitive else 0
            regex = re.compile(pattern, flags)
            
            results = []
            
            if target_path.is_file():
                files = [target_path]
            elif target_path.is_dir():
                if recursive:
                    files = list(target_path.rglob('*'))
                else:
                    files = list(target_path.glob('*'))
                files = [f for f in files if f.is_file()]
            else:
                return ToolResult(False, "", f"경로가 존재하지 않습니다: {path}")
            
            for file_path in files[:100]:  # 최대 100개 파일
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    for i, line in enumerate(content.splitlines(), 1):
                        if regex.search(line):
                            results.append(f"{file_path}:{i}: {line.strip()}")
                except Exception:
                    continue
            
            if not results:
                return ToolResult(True, "일치하는 결과가 없습니다.")
            
            output = '\n'.join(results[:50])  # 최대 50개 결과
            if len(results) > 50:
                output += f"\n... 외 {len(results) - 50}개 결과"
            
            return ToolResult(True, output)
        except Exception as e:
            return ToolResult(False, "", str(e))
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "검색할 정규식 패턴"},
                "path": {"type": "string", "description": "검색할 파일 또는 디렉토리 경로"},
                "recursive": {"type": "boolean", "description": "하위 디렉토리 포함 여부", "default": True},
                "case_insensitive": {"type": "boolean", "description": "대소문자 무시 여부", "default": False}
            },
            "required": ["pattern", "path"]
        }


class GlobTool(Tool):
    """파일 패턴 매칭 도구"""
    
    name = "Glob"
    description = "glob 패턴으로 파일을 찾습니다."
    is_readonly = True
    
    def execute(self, pattern: str, base_path: str = ".") -> ToolResult:
        """
        Args:
            pattern: glob 패턴 (예: "**/*.py")
            base_path: 기준 디렉토리
        """
        try:
            base = Path(base_path)
            if not base.exists():
                return ToolResult(False, "", f"경로가 존재하지 않습니다: {base_path}")
            
            matches = list(base.glob(pattern))
            
            if not matches:
                return ToolResult(True, "일치하는 파일이 없습니다.")
            
            output_lines = []
            for match in matches[:100]:  # 최대 100개
                stat = match.stat()
                size = stat.st_size
                output_lines.append(f"{match} ({size} bytes)")
            
            output = '\n'.join(output_lines)
            if len(matches) > 100:
                output += f"\n... 외 {len(matches) - 100}개 파일"
            
            return ToolResult(True, output)
        except Exception as e:
            return ToolResult(False, "", str(e))
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "glob 패턴 (예: **/*.py)"},
                "base_path": {"type": "string", "description": "기준 디렉토리", "default": "."}
            },
            "required": ["pattern"]
        }


class BashTool(Tool):
    """쉘 명령 실행 도구"""
    
    name = "Bash"
    description = "쉘 명령을 실행합니다."
    is_readonly = False
    
    def __init__(self, allowed_commands: Optional[List[str]] = None, timeout: int = 30):
        """
        Args:
            allowed_commands: 허용된 명령어 목록 (None이면 모든 명령 허용)
            timeout: 명령 실행 제한 시간 (초)
        """
        self.allowed_commands = allowed_commands
        self.timeout = timeout
    
    def execute(self, command: str, cwd: Optional[str] = None) -> ToolResult:
        """
        Args:
            command: 실행할 명령어
            cwd: 작업 디렉토리
        """
        # 명령어 화이트리스트 체크
        if self.allowed_commands:
            cmd_name = command.split()[0] if command else ""
            if cmd_name not in self.allowed_commands:
                return ToolResult(False, "", f"허용되지 않은 명령어: {cmd_name}")
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=cwd
            )
            
            output = result.stdout
            if result.stderr:
                output += f"\n[STDERR]\n{result.stderr}"
            
            return ToolResult(
                success=result.returncode == 0,
                output=output,
                error=None if result.returncode == 0 else f"Exit code: {result.returncode}"
            )
        except subprocess.TimeoutExpired:
            return ToolResult(False, "", f"명령 실행 시간 초과 ({self.timeout}초)")
        except Exception as e:
            return ToolResult(False, "", str(e))
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "실행할 명령어"},
                "cwd": {"type": "string", "description": "작업 디렉토리"}
            },
            "required": ["command"]
        }


class EditTool(Tool):
    """파일 편집 도구"""
    
    name = "Edit"
    description = "파일의 특정 부분을 수정합니다."
    is_readonly = False
    
    def execute(self, file_path: str, old_content: str, new_content: str) -> ToolResult:
        """
        Args:
            file_path: 편집할 파일 경로
            old_content: 대체할 기존 내용
            new_content: 새로운 내용
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return ToolResult(False, "", f"파일이 존재하지 않습니다: {file_path}")
            
            content = path.read_text(encoding='utf-8')
            
            if old_content not in content:
                return ToolResult(False, "", "대체할 텍스트를 찾을 수 없습니다")
            
            # 중복 매칭 확인
            count = content.count(old_content)
            if count > 1:
                return ToolResult(False, "", f"대체할 텍스트가 {count}번 발견되었습니다. 더 구체적인 텍스트를 지정하세요.")
            
            new_file_content = content.replace(old_content, new_content, 1)
            path.write_text(new_file_content, encoding='utf-8')
            
            return ToolResult(True, f"파일 수정 완료: {file_path}")
        except Exception as e:
            return ToolResult(False, "", str(e))
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "편집할 파일 경로"},
                "old_content": {"type": "string", "description": "대체할 기존 내용"},
                "new_content": {"type": "string", "description": "새로운 내용"}
            },
            "required": ["file_path", "old_content", "new_content"]
        }



class WriteTool(Tool):
    """파일 생성/덮어쓰기 도구"""
    
    name = "Write"
    description = "파일을 생성하거나 덮어씁니다."
    is_readonly = False
    
    def execute(self, file_path: str, content: str, overwrite: bool = False) -> ToolResult:
        """
        Args:
            file_path: 생성할 파일 경로
            content: 파일 내용
            overwrite: 기존 파일 덮어쓰기 여부
        """
        try:
            path = Path(file_path)
            
            if path.exists() and not overwrite:
                return ToolResult(False, "", f"파일이 이미 존재합니다. 덮어쓰려면 overwrite=true 설정: {file_path}")
            
            # 디렉토리 생성
            path.parent.mkdir(parents=True, exist_ok=True)
            
            path.write_text(content, encoding='utf-8')
            
            return ToolResult(True, f"파일 생성 완료: {file_path}")
        except Exception as e:
            return ToolResult(False, "", str(e))
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "생성할 파일 경로"},
                "content": {"type": "string", "description": "파일 내용"},
                "overwrite": {"type": "boolean", "description": "기존 파일 덮어쓰기 여부", "default": False}
            },
            "required": ["file_path", "content"]
        }


class TreeTool(Tool):
    """디렉토리 트리 구조 표시 도구"""
    
    name = "Tree"
    description = "디렉토리 구조를 트리 형태로 표시합니다."
    is_readonly = True
    
    def execute(self, path: str = ".", max_depth: int = 3, 
                show_hidden: bool = False, dirs_only: bool = False) -> ToolResult:
        """
        Args:
            path: 표시할 디렉토리 경로
            max_depth: 최대 깊이
            show_hidden: 숨김 파일 표시 여부
            dirs_only: 디렉토리만 표시
        """
        try:
            root_path = Path(path)
            if not root_path.exists():
                return ToolResult(False, "", f"경로가 존재하지 않습니다: {path}")
            if not root_path.is_dir():
                return ToolResult(False, "", f"디렉토리가 아닙니다: {path}")
            
            lines = [str(root_path.absolute())]
            self._build_tree(root_path, "", max_depth, 0, show_hidden, dirs_only, lines)
            
            output = '\n'.join(lines)
            return ToolResult(True, output)
        except Exception as e:
            return ToolResult(False, "", str(e))
    
    def _build_tree(self, directory: Path, prefix: str, max_depth: int, 
                    current_depth: int, show_hidden: bool, dirs_only: bool,
                    lines: List[str]) -> None:
        """트리 구조 재귀 빌드"""
        if current_depth >= max_depth:
            return
        
        try:
            entries = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except PermissionError:
            return
        
        # 숨김 파일 필터링
        if not show_hidden:
            entries = [e for e in entries if not e.name.startswith('.')]
        
        # 디렉토리만 필터링
        if dirs_only:
            entries = [e for e in entries if e.is_dir()]
        
        entries = list(entries)[:50]  # 최대 50개 항목
        
        for i, entry in enumerate(entries):
            is_last = (i == len(entries) - 1)
            connector = "└── " if is_last else "├── "
            
            if entry.is_dir():
                lines.append(f"{prefix}{connector}{entry.name}/")
                extension = "    " if is_last else "│   "
                self._build_tree(entry, prefix + extension, max_depth, 
                               current_depth + 1, show_hidden, dirs_only, lines)
            else:
                size = entry.stat().st_size
                lines.append(f"{prefix}{connector}{entry.name} ({size} bytes)")
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "표시할 디렉토리 경로", "default": "."},
                "max_depth": {"type": "integer", "description": "최대 깊이", "default": 3},
                "show_hidden": {"type": "boolean", "description": "숨김 파일 표시 여부", "default": False},
                "dirs_only": {"type": "boolean", "description": "디렉토리만 표시", "default": False}
            },
            "required": []
        }


class DiffTool(Tool):
    """파일 비교 도구"""
    
    name = "Diff"
    description = "두 파일 또는 텍스트의 차이를 비교합니다."
    is_readonly = True
    
    def execute(self, source: str, target: str, 
                context_lines: int = 3, is_file: bool = True) -> ToolResult:
        """
        Args:
            source: 원본 파일 경로 또는 텍스트
            target: 대상 파일 경로 또는 텍스트
            context_lines: 컨텍스트 줄 수
            is_file: True면 파일 경로로 처리, False면 텍스트로 처리
        """
        import difflib
        
        try:
            if is_file:
                source_path = Path(source)
                target_path = Path(target)
                
                if not source_path.exists():
                    return ToolResult(False, "", f"원본 파일이 존재하지 않습니다: {source}")
                if not target_path.exists():
                    return ToolResult(False, "", f"대상 파일이 존재하지 않습니다: {target}")
                
                source_lines = source_path.read_text(encoding='utf-8').splitlines(keepends=True)
                target_lines = target_path.read_text(encoding='utf-8').splitlines(keepends=True)
                source_name = str(source_path)
                target_name = str(target_path)
            else:
                source_lines = source.splitlines(keepends=True)
                target_lines = target.splitlines(keepends=True)
                source_name = "source"
                target_name = "target"
            
            diff = difflib.unified_diff(
                source_lines, target_lines,
                fromfile=source_name, tofile=target_name,
                n=context_lines
            )
            
            output = ''.join(diff)
            if not output:
                return ToolResult(True, "파일이 동일합니다.")
            
            return ToolResult(True, output)
        except Exception as e:
            return ToolResult(False, "", str(e))
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "원본 파일 경로 또는 텍스트"},
                "target": {"type": "string", "description": "대상 파일 경로 또는 텍스트"},
                "context_lines": {"type": "integer", "description": "컨텍스트 줄 수", "default": 3},
                "is_file": {"type": "boolean", "description": "파일 경로로 처리할지 여부", "default": True}
            },
            "required": ["source", "target"]
        }


class ListDirTool(Tool):
    """디렉토리 목록 도구"""
    
    name = "ListDir"
    description = "디렉토리의 파일/폴더 목록을 조회합니다."
    is_readonly = True
    
    def execute(self, path: str = ".", show_details: bool = False,
                show_hidden: bool = False) -> ToolResult:
        """
        Args:
            path: 조회할 디렉토리 경로
            show_details: 상세 정보 표시 (크기, 수정일)
            show_hidden: 숨김 파일 표시 여부
        """
        from datetime import datetime
        
        try:
            target_path = Path(path)
            if not target_path.exists():
                return ToolResult(False, "", f"경로가 존재하지 않습니다: {path}")
            if not target_path.is_dir():
                return ToolResult(False, "", f"디렉토리가 아닙니다: {path}")
            
            entries = sorted(target_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            
            # 숨김 파일 필터링
            if not show_hidden:
                entries = [e for e in entries if not e.name.startswith('.')]
            
            lines = []
            for entry in entries[:100]:  # 최대 100개
                if show_details:
                    try:
                        stat = entry.stat()
                        size = stat.st_size
                        mtime = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
                        entry_type = "D" if entry.is_dir() else "F"
                        lines.append(f"[{entry_type}] {entry.name:40} {size:>10} bytes  {mtime}")
                    except Exception:
                        lines.append(f"[?] {entry.name}")
                else:
                    suffix = "/" if entry.is_dir() else ""
                    lines.append(f"{entry.name}{suffix}")
            
            if len(entries) > 100:
                lines.append(f"... 외 {len(entries) - 100}개 항목")
            
            output = '\n'.join(lines) if lines else "(빈 디렉토리)"
            return ToolResult(True, output)
        except Exception as e:
            return ToolResult(False, "", str(e))
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "조회할 디렉토리 경로", "default": "."},
                "show_details": {"type": "boolean", "description": "상세 정보 표시", "default": False},
                "show_hidden": {"type": "boolean", "description": "숨김 파일 표시 여부", "default": False}
            },
            "required": []
        }


class SearchReplaceTool(Tool):
    """정규식 기반 검색 및 치환 도구"""
    
    name = "SearchReplace"
    description = "파일에서 정규식 패턴을 검색하여 일괄 치환합니다."
    is_readonly = False
    
    def execute(
        self, 
        path: str,
        pattern: str, 
        replacement: str,
        regex: bool = True,
        case_insensitive: bool = False,
        dry_run: bool = True,
        max_files: int = 10,
        file_pattern: str = "*"
    ) -> ToolResult:
        """
        Args:
            path: 검색할 파일 또는 디렉토리
            pattern: 검색 패턴 (정규식 또는 문자열)
            replacement: 치환할 내용
            regex: 정규식 사용 여부
            case_insensitive: 대소문자 무시
            dry_run: True면 변경 미리보기만, False면 실제 수정
            max_files: 최대 처리 파일 수
            file_pattern: 파일 필터 패턴 (예: *.py)
        """
        try:
            target_path = Path(path)
            
            # 파일 목록 수집
            if target_path.is_file():
                files = [target_path]
            elif target_path.is_dir():
                files = list(target_path.rglob(file_pattern))[:max_files]
                files = [f for f in files if f.is_file()]
            else:
                return ToolResult(False, "", f"경로가 존재하지 않습니다: {path}")
            
            # 정규식 컴파일
            flags = re.IGNORECASE if case_insensitive else 0
            if regex:
                search_pattern = re.compile(pattern, flags)
            else:
                # 일반 문자열 검색을 위해 이스케이프
                search_pattern = re.compile(re.escape(pattern), flags)
            
            results = []
            total_matches = 0
            
            for file_path in files:
                try:
                    content = file_path.read_text(encoding='utf-8')
                    matches = list(search_pattern.finditer(content))
                    
                    if not matches:
                        continue
                    
                    total_matches += len(matches)
                    new_content = search_pattern.sub(replacement, content)
                    
                    # 변경 사항 미리보기
                    file_result = f"\n📄 {file_path} ({len(matches)}개 매칭)"
                    
                    for match in matches[:5]:  # 파일당 최대 5개 미리보기
                        start = max(0, match.start() - 20)
                        end = min(len(content), match.end() + 20)
                        context = content[start:end].replace('\n', '↵')
                        file_result += f"\n  - ...{context}..."
                    
                    if len(matches) > 5:
                        file_result += f"\n  ... 외 {len(matches) - 5}개"
                    
                    results.append(file_result)
                    
                    # 실제 수정
                    if not dry_run:
                        file_path.write_text(new_content, encoding='utf-8')
                        
                except Exception as e:
                    results.append(f"\n⚠️ {file_path}: {e}")
            
            if not results:
                return ToolResult(True, "일치하는 패턴이 없습니다.")
            
            mode_text = "[DRY-RUN] 미리보기 모드" if dry_run else "[APPLIED] 수정 완료"
            header = f"{mode_text}\n총 {total_matches}개 매칭, {len(results)}개 파일"
            
            if dry_run:
                header += "\n\n💡 실제 수정하려면 dry_run=false로 다시 실행하세요."
            
            output = header + '\n' + '\n'.join(results)
            return ToolResult(True, output)
            
        except re.error as e:
            return ToolResult(False, "", f"정규식 오류: {e}")
        except Exception as e:
            return ToolResult(False, "", str(e))
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "검색할 파일 또는 디렉토리"},
                "pattern": {"type": "string", "description": "검색 패턴 (정규식 또는 문자열)"},
                "replacement": {"type": "string", "description": "치환할 내용"},
                "regex": {"type": "boolean", "description": "정규식 사용 여부", "default": True},
                "case_insensitive": {"type": "boolean", "description": "대소문자 무시", "default": False},
                "dry_run": {"type": "boolean", "description": "미리보기만 (기본값: true)", "default": True},
                "max_files": {"type": "integer", "description": "최대 처리 파일 수", "default": 10},
                "file_pattern": {"type": "string", "description": "파일 필터 패턴", "default": "*"}
            },
            "required": ["path", "pattern", "replacement"]
        }


class ToolRegistry:
    """도구 레지스트리"""
    
    def __init__(self):
        """모든 기본 도구 등록"""
        self._tools: Dict[str, Tool] = {}
        
        # 기본 도구 등록
        self.register(ReadTool())
        self.register(GrepTool())
        self.register(GlobTool())
        self.register(BashTool())
        self.register(EditTool())
        self.register(WriteTool())
        
        # 확장 도구 등록
        self.register(TreeTool())
        self.register(DiffTool())
        self.register(ListDirTool())
        self.register(SearchReplaceTool())

    
    def register(self, tool: Tool) -> None:
        """도구 등록"""
        self._tools[tool.name] = tool
    
    def get(self, name: str) -> Optional[Tool]:
        """이름으로 도구 가져오기"""
        return self._tools.get(name)
    
    def get_allowed_tools(self, tool_names: List[str]) -> Dict[str, Tool]:
        """
        허용된 도구만 필터링하여 반환
        
        Args:
            tool_names: 허용할 도구 이름 목록
            
        Returns:
            {도구 이름: Tool 인스턴스} 딕셔너리
        """
        if not tool_names:
            # 도구 목록이 비어있으면 모든 도구 반환
            return dict(self._tools)
        
        return {
            name: tool 
            for name, tool in self._tools.items() 
            if name in tool_names
        }
    
    def get_readonly_tools(self) -> Dict[str, Tool]:
        """읽기 전용 도구만 반환"""
        return {
            name: tool 
            for name, tool in self._tools.items() 
            if tool.is_readonly
        }
    
    def get_all_schemas(self, tool_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """LLM function calling용 스키마 목록 반환"""
        tools = self.get_allowed_tools(tool_names) if tool_names else self._tools
        return [tool.get_schema() for tool in tools.values()]
    
    @property
    def available_tools(self) -> List[str]:
        """사용 가능한 도구 이름 목록"""
        return list(self._tools.keys())
