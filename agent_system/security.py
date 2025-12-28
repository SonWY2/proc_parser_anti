"""
보안 모듈

파일 접근 제한 및 명령어 샌드박스를 제공합니다.
"""

import re
from pathlib import Path
from typing import List, Optional, Set, Tuple
from dataclasses import dataclass, field


@dataclass
class FileAccessControl:
    """파일 접근 제어
    
    허용/거부 경로 목록과 확장자 필터를 통해 파일 접근을 제어합니다.
    """
    
    allowed_paths: List[str] = field(default_factory=list)
    denied_paths: List[str] = field(default_factory=list)
    allowed_extensions: Set[str] = field(default_factory=set)
    
    def __post_init__(self):
        # 경로를 절대 경로로 변환
        self._allowed_resolved = [Path(p).resolve() for p in self.allowed_paths]
        self._denied_resolved = [Path(p).resolve() for p in self.denied_paths]
    
    def is_allowed(self, path: str) -> bool:
        """
        경로 접근 허용 여부 확인
        
        Args:
            path: 확인할 경로
            
        Returns:
            접근 허용 여부
        """
        try:
            target = Path(path).resolve()
        except Exception:
            return False
        
        # 거부 목록 확인 (우선)
        for denied in self._denied_resolved:
            if target == denied or self._is_subpath(target, denied):
                return False
        
        # 확장자 확인
        if self.allowed_extensions:
            if target.is_file() and target.suffix.lstrip('.') not in self.allowed_extensions:
                return False
        
        # 허용 목록이 비어있으면 모든 접근 허용
        if not self._allowed_resolved:
            return True
        
        # 허용 목록 확인
        for allowed in self._allowed_resolved:
            if target == allowed or self._is_subpath(target, allowed):
                return True
        
        return False
    
    def _is_subpath(self, path: Path, parent: Path) -> bool:
        """path가 parent의 하위 경로인지 확인"""
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False
    
    def add_allowed(self, path: str) -> None:
        """허용 경로 추가"""
        resolved = Path(path).resolve()
        if resolved not in self._allowed_resolved:
            self.allowed_paths.append(path)
            self._allowed_resolved.append(resolved)
    
    def add_denied(self, path: str) -> None:
        """거부 경로 추가"""
        resolved = Path(path).resolve()
        if resolved not in self._denied_resolved:
            self.denied_paths.append(path)
            self._denied_resolved.append(resolved)


@dataclass
class CommandSandbox:
    """명령어 샌드박스
    
    위험한 명령어 실행을 방지합니다.
    """
    
    # 기본 위험 명령어
    DEFAULT_DANGEROUS_COMMANDS: Set[str] = field(default_factory=lambda: {
        # 삭제 명령
        'rm', 'rmdir', 'del', 'rd', 'erase',
        # 포맷/파티션
        'format', 'mkfs', 'fdisk', 'diskpart',
        # 시스템
        'shutdown', 'reboot', 'halt', 'poweroff', 'init',
        # 권한
        'chmod', 'chown', 'sudo', 'su',
        # 네트워크 (선택적)
        # 'curl', 'wget', 'nc', 'netcat',
    })
    
    # 기본 위험 패턴
    DEFAULT_DANGEROUS_PATTERNS: List[str] = field(default_factory=lambda: [
        r'>\s*/dev/',              # 디바이스 쓰기
        r'rm\s+(-rf?|--force)\s+/', # 루트 삭제
        r':\(\)\{\s*:\|:&\s*\};:',  # Fork bomb
        r'dd\s+.*of=/dev/',        # 디스크 직접 쓰기
        r'\|.*sh\s*$',             # 파이프를 통한 쉘 실행
        r'eval\s+.*\$',            # eval 명령
        r'>\s*/etc/',              # 시스템 설정 덮어쓰기
    ])
    
    allowed_commands: Set[str] = field(default_factory=set)
    blocked_commands: Set[str] = field(default_factory=set)
    blocked_patterns: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        # 기본 차단 목록 병합
        if not self.blocked_commands:
            self.blocked_commands = self.DEFAULT_DANGEROUS_COMMANDS.copy()
        if not self.blocked_patterns:
            self.blocked_patterns = self.DEFAULT_DANGEROUS_PATTERNS.copy()
        
        # 패턴 컴파일
        self._compiled_patterns = [
            re.compile(pattern, re.IGNORECASE) 
            for pattern in self.blocked_patterns
        ]
    
    def is_safe(self, command: str) -> Tuple[bool, str]:
        """
        명령어 안전성 확인
        
        Args:
            command: 확인할 명령어
            
        Returns:
            (안전 여부, 거부 사유)
        """
        if not command or not command.strip():
            return True, ""
        
        cmd_parts = command.strip().split()
        base_cmd = cmd_parts[0].lower()
        
        # 경로에서 명령어 이름만 추출
        if '/' in base_cmd or '\\' in base_cmd:
            base_cmd = Path(base_cmd).name.lower()
        
        # 화이트리스트 모드 (허용 목록이 설정된 경우)
        if self.allowed_commands:
            if base_cmd not in self.allowed_commands:
                return False, f"허용되지 않은 명령어: {base_cmd}"
            return True, ""
        
        # 블랙리스트 체크
        if base_cmd in self.blocked_commands:
            return False, f"차단된 명령어: {base_cmd}"
        
        # 위험 패턴 체크
        for i, pattern in enumerate(self._compiled_patterns):
            if pattern.search(command):
                return False, f"위험한 패턴 감지됨"
        
        return True, ""
    
    def add_allowed(self, command: str) -> None:
        """허용 명령어 추가 (화이트리스트 모드)"""
        self.allowed_commands.add(command.lower())
    
    def add_blocked(self, command: str) -> None:
        """차단 명령어 추가"""
        self.blocked_commands.add(command.lower())
    
    def add_blocked_pattern(self, pattern: str) -> None:
        """차단 패턴 추가"""
        self.blocked_patterns.append(pattern)
        self._compiled_patterns.append(re.compile(pattern, re.IGNORECASE))


class SecurityManager:
    """보안 관리자
    
    파일 접근 제어와 명령어 샌드박스를 통합 관리합니다.
    """
    
    def __init__(
        self,
        file_access: Optional[FileAccessControl] = None,
        command_sandbox: Optional[CommandSandbox] = None
    ):
        self.file_access = file_access or FileAccessControl()
        self.command_sandbox = command_sandbox or CommandSandbox()
    
    def check_file_access(self, path: str) -> Tuple[bool, str]:
        """파일 접근 확인"""
        if self.file_access.is_allowed(path):
            return True, ""
        return False, f"접근 거부: {path}"
    
    def check_command(self, command: str) -> Tuple[bool, str]:
        """명령어 확인"""
        return self.command_sandbox.is_safe(command)
    
    @classmethod
    def create_readonly(cls) -> 'SecurityManager':
        """읽기 전용 보안 관리자 생성"""
        sandbox = CommandSandbox(
            allowed_commands={'ls', 'dir', 'cat', 'type', 'head', 'tail', 
                            'grep', 'find', 'tree', 'pwd', 'echo', 'wc'}
        )
        return cls(command_sandbox=sandbox)
    
    @classmethod
    def create_project_scoped(cls, project_path: str) -> 'SecurityManager':
        """프로젝트 범위 보안 관리자 생성"""
        file_access = FileAccessControl(
            allowed_paths=[project_path],
            denied_paths=[
                str(Path(project_path) / '.git'),
                str(Path(project_path) / '.env'),
                str(Path(project_path) / 'secrets'),
            ]
        )
        return cls(file_access=file_access)
