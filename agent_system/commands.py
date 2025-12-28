"""
슬래시 명령어 시스템

워크플로우를 명령어로 패키징하여 쉽게 실행합니다.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from pathlib import Path
import re

if TYPE_CHECKING:
    from .workflow import WorkflowEngine, WorkflowResult


@dataclass
class SlashCommand:
    """슬래시 명령어 정의"""
    name: str                                   # 예: "convert-proc"
    description: str = ""
    workflow: str = ""                          # 실행할 워크플로우 이름
    arguments: List[str] = field(default_factory=list)  # 필수 인자
    defaults: Dict[str, Any] = field(default_factory=dict)  # 기본값
    help_text: str = ""                         # 도움말 텍스트


class CommandRegistry:
    """명령어 레지스트리"""
    
    COMMAND_DIR = ".agents/commands"
    
    def __init__(self, workflow_engine: Optional['WorkflowEngine'] = None):
        self.engine = workflow_engine
        self.commands: Dict[str, SlashCommand] = {}
        self._register_builtins()
    
    def _register_builtins(self) -> None:
        """기본 명령어 등록"""
        self.register(SlashCommand(
            name="help",
            description="도움말 표시",
            help_text="사용법: /help [command]"
        ))
        self.register(SlashCommand(
            name="agents",
            description="에이전트 목록 표시"
        ))
        self.register(SlashCommand(
            name="workflows",
            description="워크플로우 목록 표시"
        ))
        self.register(SlashCommand(
            name="status",
            description="현재 실행 상태 표시"
        ))
    
    def register(self, command: SlashCommand) -> None:
        """명령어 등록"""
        self.commands[command.name] = command
    
    def unregister(self, name: str) -> bool:
        """명령어 해제"""
        if name in self.commands:
            del self.commands[name]
            return True
        return False
    
    def get(self, name: str) -> Optional[SlashCommand]:
        """명령어 조회"""
        return self.commands.get(name)
    
    def list_commands(self) -> List[Dict[str, str]]:
        """명령어 목록"""
        return [
            {
                "name": f"/{cmd.name}",
                "description": cmd.description,
                "workflow": cmd.workflow
            }
            for cmd in self.commands.values()
        ]
    
    def load_from_file(self, file_path: str) -> Optional[SlashCommand]:
        """
        파일에서 명령어 로드
        
        파일 형식:
        ---
        name: convert-proc
        description: Pro*C to Java 변환
        workflow: convert-proc
        arguments: [target_dir]
        defaults:
          output_dir: ./output
        ---
        (도움말 텍스트)
        """
        path = Path(file_path)
        if not path.exists():
            return None
        
        content = path.read_text(encoding='utf-8')
        
        # YAML frontmatter 파싱 (간단한 구현)
        if not content.startswith('---'):
            return None
        
        parts = content.split('---', 2)
        if len(parts) < 3:
            return None
        
        frontmatter = parts[1].strip()
        help_text = parts[2].strip() if len(parts) > 2 else ""
        
        # 간단한 YAML 파싱
        meta = {}
        for line in frontmatter.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                # 리스트 파싱
                if value.startswith('[') and value.endswith(']'):
                    value = [v.strip() for v in value[1:-1].split(',')]
                
                meta[key] = value
        
        command = SlashCommand(
            name=meta.get('name', path.stem),
            description=meta.get('description', ''),
            workflow=meta.get('workflow', ''),
            arguments=meta.get('arguments', []) if isinstance(meta.get('arguments'), list) else [],
            defaults=meta.get('defaults', {}),
            help_text=help_text
        )
        
        self.register(command)
        return command
    
    def load_from_directory(self, base_path: str = ".") -> int:
        """
        디렉토리에서 명령어 로드
        
        Returns:
            로드된 명령어 수
        """
        command_dir = Path(base_path) / self.COMMAND_DIR
        if not command_dir.exists():
            return 0
        
        count = 0
        for file_path in command_dir.glob("*.md"):
            if self.load_from_file(str(file_path)):
                count += 1
        
        return count
    
    def parse(self, input_text: str) -> tuple[Optional[str], Dict[str, Any]]:
        """
        입력 텍스트 파싱
        
        Args:
            input_text: 사용자 입력 (예: "/convert-proc ./src --output ./out")
            
        Returns:
            (명령어 이름, 인자 딕셔너리) 또는 (None, {})
        """
        if not input_text.startswith('/'):
            return None, {}
        
        parts = input_text[1:].split()
        if not parts:
            return None, {}
        
        command_name = parts[0]
        args: Dict[str, Any] = {}
        
        # 위치 인자와 키워드 인자 파싱
        positional = []
        i = 1
        while i < len(parts):
            part = parts[i]
            if part.startswith('--'):
                key = part[2:]
                if i + 1 < len(parts) and not parts[i + 1].startswith('--'):
                    args[key] = parts[i + 1]
                    i += 2
                else:
                    args[key] = True
                    i += 1
            else:
                positional.append(part)
                i += 1
        
        # 위치 인자를 명령어의 arguments에 매핑
        command = self.get(command_name)
        if command and command.arguments:
            for j, arg_name in enumerate(command.arguments):
                if j < len(positional):
                    args[arg_name] = positional[j]
        
        return command_name, args
    
    def execute(self, command_name: str, args: Dict[str, Any]) -> Optional['WorkflowResult']:
        """
        명령어 실행
        
        Args:
            command_name: 명령어 이름
            args: 인자 딕셔너리
            
        Returns:
            워크플로우 결과 또는 None
        """
        command = self.get(command_name)
        if not command:
            raise ValueError(f"알 수 없는 명령어: {command_name}")
        
        if not command.workflow:
            # 내장 명령어
            return None
        
        if not self.engine:
            raise RuntimeError("WorkflowEngine이 설정되지 않았습니다")
        
        # 기본값과 인자 병합
        context = {**command.defaults, **args}
        
        return self.engine.execute(command.workflow, context=context)
    
    def get_help(self, command_name: Optional[str] = None) -> str:
        """도움말 텍스트 반환"""
        if command_name:
            command = self.get(command_name)
            if not command:
                return f"알 수 없는 명령어: {command_name}"
            
            lines = [
                f"/{command.name} - {command.description}",
                ""
            ]
            
            if command.arguments:
                lines.append("인자:")
                for arg in command.arguments:
                    default = command.defaults.get(arg, "필수")
                    lines.append(f"  {arg}: {default}")
            
            if command.help_text:
                lines.append("")
                lines.append(command.help_text)
            
            return '\n'.join(lines)
        
        # 전체 도움말
        lines = ["사용 가능한 명령어:", ""]
        for cmd in self.commands.values():
            lines.append(f"  /{cmd.name:20} {cmd.description}")
        
        return '\n'.join(lines)
