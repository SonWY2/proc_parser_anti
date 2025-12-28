"""
Interactive CLI

Claude Code 스타일의 대화형 터미널 인터페이스를 제공합니다.
"""

import sys
from typing import Optional, TYPE_CHECKING

# 선택적 의존성
try:
    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

if TYPE_CHECKING:
    from .orchestrator import Orchestrator
    from .workflow import WorkflowEngine
    from .commands import CommandRegistry


class InteractiveCLI:
    """대화형 CLI 인터페이스"""
    
    COMMANDS = {
        '/help': '도움말 표시',
        '/agents': '에이전트 목록',
        '/workflows': '워크플로우 목록',
        '/run <workflow>': '워크플로우 실행',
        '/resume': '일시정지된 워크플로우 재개',
        '/status': '실행 중인 작업 상태',
        '/approve': '대기 중인 체크포인트 승인',
        '/reject': '체크포인트 거부',
        '/quit': '종료',
    }
    
    def __init__(
        self, 
        orchestrator: 'Orchestrator', 
        workflow_engine: Optional['WorkflowEngine'] = None,
        command_registry: Optional['CommandRegistry'] = None
    ):
        self.orchestrator = orchestrator
        self.engine = workflow_engine
        self.cmd_registry = command_registry
        self.running = True
        
        if HAS_RICH:
            self.console = Console()
        else:
            self.console = None
        
        if HAS_PROMPT_TOOLKIT:
            self.history = FileHistory('.agent_cli_history')
        else:
            self.history = None
    
    def print(self, message: str, style: str = "") -> None:
        """출력"""
        if self.console:
            self.console.print(message, style=style)
        else:
            print(message)
    
    def print_panel(self, content: str, title: str = "") -> None:
        """패널 출력"""
        if self.console and HAS_RICH:
            self.console.print(Panel(content, title=title))
        else:
            print(f"=== {title} ===")
            print(content)
            print("=" * 40)
    
    def print_table(self, title: str, columns: list, rows: list) -> None:
        """테이블 출력"""
        if self.console and HAS_RICH:
            table = Table(title=title)
            for col in columns:
                table.add_column(col)
            for row in rows:
                table.add_row(*[str(v) for v in row])
            self.console.print(table)
        else:
            print(f"\n{title}")
            print("-" * 40)
            for row in rows:
                print("  ".join(str(v) for v in row))
    
    def get_input(self, prompt_text: str = ">>> ") -> str:
        """입력 받기"""
        if HAS_PROMPT_TOOLKIT and self.history:
            return pt_prompt(
                prompt_text,
                history=self.history,
                auto_suggest=AutoSuggestFromHistory()
            )
        else:
            return input(prompt_text)
    
    def run(self) -> None:
        """CLI 메인 루프"""
        self.print_panel("Agent System CLI", title="Welcome")
        self.print("'/help'를 입력하여 명령어 목록을 확인하세요.\n")
        
        while self.running:
            try:
                user_input = self.get_input(">>> ")
                self._handle_input(user_input)
            except KeyboardInterrupt:
                self.print("\n[Ctrl+C] 종료하려면 /quit 입력", style="yellow")
            except EOFError:
                break
            except Exception as e:
                self.print(f"오류: {e}", style="red")
    
    def _handle_input(self, text: str) -> None:
        """입력 처리"""
        text = text.strip()
        if not text:
            return
        
        if text.startswith('/'):
            self._handle_command(text)
        else:
            self._run_task(text)
    
    def _handle_command(self, cmd: str) -> None:
        """슬래시 명령어 처리"""
        parts = cmd.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        if command == '/quit' or command == '/exit':
            self.running = False
            self.print("종료합니다.", style="bold")
        elif command == '/help':
            self._show_help(args)
        elif command == '/agents':
            self._show_agents()
        elif command == '/workflows':
            self._show_workflows()
        elif command == '/run':
            self._run_workflow(args)
        elif command == '/status':
            self._show_status()
        elif command == '/approve':
            self._handle_approval(True)
        elif command == '/reject':
            self._handle_approval(False)
        elif command == '/resume':
            self._show_resume_options()
        else:
            # 커스텀 명령어 시도
            if self.cmd_registry:
                cmd_name, cmd_args = self.cmd_registry.parse(cmd)
                if cmd_name and self.cmd_registry.get(cmd_name):
                    try:
                        result = self.cmd_registry.execute(cmd_name, cmd_args)
                        if result:
                            self.print_panel(result.summary(), title=f"/{cmd_name}")
                        return
                    except Exception as e:
                        self.print(f"명령어 실행 오류: {e}", style="red")
                        return
            
            self.print(f"알 수 없는 명령어: {command}", style="red")
            self.print("'/help'를 입력하여 사용 가능한 명령어를 확인하세요.")
    
    def _show_help(self, args: str = "") -> None:
        """도움말 표시"""
        if self.cmd_registry and args:
            help_text = self.cmd_registry.get_help(args)
            self.print(help_text)
            return
        
        rows = [(cmd, desc) for cmd, desc in self.COMMANDS.items()]
        self.print_table("사용 가능한 명령어", ["명령어", "설명"], rows)
    
    def _show_agents(self) -> None:
        """에이전트 목록"""
        agents = self.orchestrator.list_agents()
        if not agents:
            self.print("로드된 에이전트가 없습니다.", style="yellow")
            return
        
        rows = [(a['name'], a['description'][:50], ', '.join(a.get('tools', [])[:3])) 
                for a in agents]
        self.print_table("에이전트 목록", ["이름", "설명", "도구"], rows)
    
    def _show_workflows(self) -> None:
        """워크플로우 목록"""
        if not self.engine:
            self.print("WorkflowEngine이 설정되지 않았습니다.", style="yellow")
            return
        
        workflows = self.engine.list_workflows()
        if not workflows:
            self.print("등록된 워크플로우가 없습니다.", style="yellow")
            return
        
        rows = [(w['name'], w.get('description', '')[:50], w.get('steps', 0)) 
                for w in workflows]
        self.print_table("워크플로우 목록", ["이름", "설명", "단계 수"], rows)
    
    def _run_workflow(self, workflow_name: str) -> None:
        """워크플로우 실행"""
        if not workflow_name:
            self.print("사용법: /run <workflow_name>", style="yellow")
            return
        
        if not self.engine:
            self.print("WorkflowEngine이 설정되지 않았습니다.", style="yellow")
            return
        
        self.print(f"워크플로우 실행 중: {workflow_name}", style="bold")
        
        if HAS_RICH and self.console:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                progress.add_task(description="실행 중...", total=None)
                result = self.engine.execute(workflow_name)
        else:
            result = self.engine.execute(workflow_name)
        
        self.print_panel(result.summary(), title=f"워크플로우: {workflow_name}")
    
    def _run_task(self, task: str) -> None:
        """에이전트에 작업 위임"""
        self.print("에이전트 실행 중...", style="dim")
        
        result = self.orchestrator.auto_delegate(task)
        
        if result and result.success:
            self.print_panel(result.output, title=f"[{result.agent_name}]")
        elif result:
            self.print(f"오류: {result.error}", style="red")
        else:
            self.print("적합한 에이전트를 찾을 수 없습니다.", style="yellow")
    
    def _show_status(self) -> None:
        """현재 상태"""
        agents = self.orchestrator.list_agents()
        self.print(f"로드된 에이전트: {len(agents)}개")
        
        if self.engine:
            workflows = self.engine.list_workflows()
            self.print(f"등록된 워크플로우: {len(workflows)}개")
            
            pending = self.engine.checkpoint_manager.list_pending() if hasattr(self.engine, 'checkpoint_manager') else []
            if pending:
                self.print(f"승인 대기 중: {len(pending)}개 - {pending}")
    
    def _handle_approval(self, approve: bool) -> None:
        """체크포인트 승인/거부"""
        if not self.engine or not hasattr(self.engine, 'checkpoint_manager'):
            self.print("체크포인트 관리자가 없습니다.", style="yellow")
            return
        
        if approve:
            state = self.engine.checkpoint_manager.approve_current()
            if state:
                self.print(f"승인됨: {state.workflow_name}", style="green")
            else:
                self.print("승인 대기 중인 요청이 없습니다.", style="yellow")
        else:
            reason = self.get_input("거부 사유: ")
            state = self.engine.checkpoint_manager.reject_current(reason)
            if state:
                self.print(f"거부됨: {state.workflow_name}", style="red")
            else:
                self.print("승인 대기 중인 요청이 없습니다.", style="yellow")
    
    def _show_resume_options(self) -> None:
        """재개 가능한 워크플로우 표시"""
        if not self.engine or not hasattr(self.engine, 'checkpoint_manager'):
            self.print("체크포인트 관리자가 없습니다.", style="yellow")
            return
        
        saved = self.engine.checkpoint_manager.list_saved_states()
        if not saved:
            self.print("저장된 워크플로우 상태가 없습니다.", style="yellow")
            return
        
        self.print("저장된 상태 파일:")
        for i, path in enumerate(saved, 1):
            self.print(f"  {i}. {path}")


def run_cli(orchestrator: 'Orchestrator', **kwargs) -> None:
    """CLI 실행 헬퍼 함수"""
    cli = InteractiveCLI(orchestrator, **kwargs)
    cli.run()
