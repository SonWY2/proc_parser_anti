"""
Tkinter GUI

워크플로우 실행 상태를 시각화하고 사용자 제어를 제공합니다.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
from threading import Thread
from typing import Optional, Callable, TYPE_CHECKING, List
from datetime import datetime

if TYPE_CHECKING:
    from .orchestrator import Orchestrator
    from .workflow import WorkflowEngine, WorkflowResult


class WorkflowGUI:
    """워크플로우 GUI"""
    
    def __init__(
        self, 
        orchestrator: 'Orchestrator', 
        workflow_engine: Optional['WorkflowEngine'] = None
    ):
        self.orchestrator = orchestrator
        self.engine = workflow_engine
        
        self.root = tk.Tk()
        self.root.title("Agent Workflow Monitor")
        self.root.geometry("1100x750")
        
        # 상태 변수
        self._running_workflow: Optional[str] = None
        self._log_buffer: List[str] = []
        
        self._setup_ui()
        self._setup_menu()
        self._refresh_lists()
    
    def _setup_menu(self) -> None:
        """메뉴바 설정"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File 메뉴
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Load Workflow...", command=self._load_workflow_file)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # View 메뉴
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Refresh", command=self._refresh_lists)
        view_menu.add_command(label="Clear Log", command=self._clear_log)
    
    def _setup_ui(self) -> None:
        """UI 구성"""
        # === 좌측: 에이전트/워크플로우 목록 ===
        left_frame = ttk.Frame(self.root, width=280)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        left_frame.pack_propagate(False)
        
        # 워크플로우 섹션
        wf_label = ttk.Label(left_frame, text="📋 Workflows", font=("", 11, "bold"))
        wf_label.pack(anchor="w", pady=(0, 5))
        
        self.workflow_list = tk.Listbox(left_frame, height=8, selectmode=tk.SINGLE)
        self.workflow_list.pack(fill=tk.X, pady=(0, 10))
        self.workflow_list.bind('<<ListboxSelect>>', self._on_workflow_select)
        
        # 에이전트 섹션
        agent_label = ttk.Label(left_frame, text="🤖 Agents", font=("", 11, "bold"))
        agent_label.pack(anchor="w", pady=(0, 5))
        
        self.agent_list = tk.Listbox(left_frame, height=8, selectmode=tk.SINGLE)
        self.agent_list.pack(fill=tk.X, pady=(0, 10))
        
        # 버튼
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        self.run_btn = ttk.Button(btn_frame, text="▶ Run", command=self._run_selected)
        self.run_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        self.stop_btn = ttk.Button(btn_frame, text="⏹ Stop", command=self._stop, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        # 태스크 실행
        ttk.Separator(left_frame, orient='horizontal').pack(fill=tk.X, pady=10)
        
        ttk.Label(left_frame, text="💬 Quick Task", font=("", 10, "bold")).pack(anchor="w")
        self.task_entry = ttk.Entry(left_frame)
        self.task_entry.pack(fill=tk.X, pady=5)
        self.task_entry.bind('<Return>', lambda e: self._run_quick_task())
        
        ttk.Button(left_frame, text="Run Task", command=self._run_quick_task).pack(fill=tk.X)
        
        # === 중앙: 워크플로우 진행 상황 ===
        center_frame = ttk.Frame(self.root)
        center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 진행 상태
        progress_frame = ttk.LabelFrame(center_frame, text="Progress")
        progress_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.status_label = ttk.Label(progress_frame, text="Ready", font=("", 10))
        self.status_label.pack(anchor="w", padx=5, pady=2)
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate')
        self.progress_bar.pack(fill=tk.X, padx=5, pady=5)
        
        self.step_label = ttk.Label(progress_frame, text="", foreground="gray")
        self.step_label.pack(anchor="w", padx=5, pady=2)
        
        # 워크플로우 시각화 캔버스
        canvas_frame = ttk.LabelFrame(center_frame, text="Workflow Visualization")
        canvas_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.canvas = tk.Canvas(canvas_frame, bg="white", height=150)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 출력 로그
        log_frame = ttk.LabelFrame(center_frame, text="Output Log")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, state='disabled', wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # === 우측: 체크포인트 승인 ===
        right_frame = ttk.Frame(self.root, width=220)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)
        right_frame.pack_propagate(False)
        
        ttk.Label(right_frame, text="⏸ Pending Approvals", font=("", 11, "bold")).pack(anchor="w", pady=(0, 5))
        
        self.approval_list = tk.Listbox(right_frame, height=6)
        self.approval_list.pack(fill=tk.X, pady=(0, 10))
        
        # 승인/거부 버튼
        approval_btn_frame = ttk.Frame(right_frame)
        approval_btn_frame.pack(fill=tk.X)
        
        self.approve_btn = ttk.Button(approval_btn_frame, text="✓ Approve", command=self._approve)
        self.approve_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        self.reject_btn = ttk.Button(approval_btn_frame, text="✗ Reject", command=self._reject)
        self.reject_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        # 상세 정보
        ttk.Separator(right_frame, orient='horizontal').pack(fill=tk.X, pady=10)
        
        ttk.Label(right_frame, text="ℹ Details", font=("", 10, "bold")).pack(anchor="w")
        self.detail_text = scrolledtext.ScrolledText(right_frame, height=10, state='disabled', wrap=tk.WORD)
        self.detail_text.pack(fill=tk.BOTH, expand=True, pady=5)
    
    def _log(self, message: str, level: str = "INFO") -> None:
        """로그 추가"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] [{level}] {message}"
        
        self._log_buffer.append(formatted)
        
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, f"{formatted}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')
    
    def _clear_log(self) -> None:
        """로그 초기화"""
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state='disabled')
        self._log_buffer.clear()
    
    def _update_status(self, text: str) -> None:
        """상태 레이블 업데이트 (thread-safe)"""
        self.root.after(0, lambda: self.status_label.config(text=text))
    
    def _update_progress(self, value: int, step_info: str = "") -> None:
        """진행률 업데이트 (thread-safe)"""
        self.root.after(0, lambda: self.progress_bar.config(value=value))
        if step_info:
            self.root.after(0, lambda: self.step_label.config(text=step_info))
    
    def _on_workflow_select(self, event) -> None:
        """워크플로우 선택 시"""
        selection = self.workflow_list.curselection()
        if not selection:
            return
        
        workflow_name = self.workflow_list.get(selection[0])
        self._show_workflow_detail(workflow_name)
    
    def _show_workflow_detail(self, name: str) -> None:
        """워크플로우 상세 표시"""
        self.detail_text.config(state='normal')
        self.detail_text.delete(1.0, tk.END)
        
        if self.engine:
            workflow = self.engine.workflows.get(name)
            if workflow:
                self.detail_text.insert(tk.END, f"Name: {workflow.name}\n")
                self.detail_text.insert(tk.END, f"Description: {workflow.description}\n")
                self.detail_text.insert(tk.END, f"Steps: {len(workflow.steps)}\n\n")
                
                for i, step in enumerate(workflow.steps, 1):
                    self.detail_text.insert(tk.END, f"{i}. {step.name} → {step.agent}\n")
        
        self.detail_text.config(state='disabled')
    
    def _draw_workflow(self, workflow_name: str, current_step: int = -1) -> None:
        """워크플로우 시각화"""
        self.canvas.delete("all")
        
        if not self.engine:
            return
        
        workflow = self.engine.workflows.get(workflow_name)
        if not workflow or not workflow.steps:
            return
        
        # 캔버스 크기
        width = self.canvas.winfo_width() or 600
        height = self.canvas.winfo_height() or 150
        
        # 단계별 위치 계산
        step_count = len(workflow.steps)
        step_width = min(80, (width - 40) // step_count)
        start_x = 20
        y = height // 2
        
        for i, step in enumerate(workflow.steps):
            x = start_x + i * (step_width + 20)
            
            # 색상 결정
            if i < current_step:
                color = "#90EE90"  # 완료: 연두색
            elif i == current_step:
                color = "#FFD700"  # 현재: 노란색
            else:
                color = "#E0E0E0"  # 대기: 회색
            
            # 박스 그리기
            self.canvas.create_rectangle(
                x, y - 25, x + step_width, y + 25,
                fill=color, outline="#333"
            )
            
            # 텍스트
            display_name = step.name[:10] + "..." if len(step.name) > 10 else step.name
            self.canvas.create_text(
                x + step_width // 2, y,
                text=display_name, font=("", 8)
            )
            
            # 화살표
            if i < step_count - 1:
                self.canvas.create_line(
                    x + step_width, y, x + step_width + 20, y,
                    arrow=tk.LAST
                )
    
    def _run_selected(self) -> None:
        """선택된 워크플로우 실행"""
        selection = self.workflow_list.curselection()
        if not selection:
            messagebox.showwarning("Warning", "워크플로우를 선택하세요")
            return
        
        workflow_name = self.workflow_list.get(selection[0])
        self._run_workflow_async(workflow_name)
    
    def _run_workflow_async(self, name: str) -> None:
        """워크플로우 비동기 실행"""
        if not self.engine:
            messagebox.showerror("Error", "WorkflowEngine이 설정되지 않았습니다")
            return
        
        self._running_workflow = name
        self.run_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        
        self._log(f"워크플로우 시작: {name}")
        self._update_status(f"Running: {name}")
        self._draw_workflow(name, 0)
        
        # 별도 스레드에서 실행
        thread = Thread(target=self._execute_workflow, args=(name,), daemon=True)
        thread.start()
    
    def _execute_workflow(self, name: str) -> None:
        """워크플로우 실행 (별도 스레드)"""
        try:
            result = self.engine.execute(name)
            self.root.after(0, lambda: self._on_workflow_complete(result))
        except Exception as e:
            self.root.after(0, lambda: self._on_workflow_error(str(e)))
    
    def _on_workflow_complete(self, result: 'WorkflowResult') -> None:
        """워크플로우 완료 콜백"""
        self._running_workflow = None
        self.run_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        
        if result.success:
            self._log(f"워크플로우 완료: {result.workflow_name}", "SUCCESS")
            self._update_status("Completed ✓")
            self._update_progress(100, f"완료: {len(result.steps_executed)}개 단계")
        else:
            self._log(f"워크플로우 실패: {result.errors}", "ERROR")
            self._update_status("Failed ✗")
        
        # 결과 상세 표시
        self.detail_text.config(state='normal')
        self.detail_text.delete(1.0, tk.END)
        self.detail_text.insert(tk.END, result.summary())
        self.detail_text.config(state='disabled')
    
    def _on_workflow_error(self, error: str) -> None:
        """워크플로우 오류 콜백"""
        self._running_workflow = None
        self.run_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        
        self._log(f"오류: {error}", "ERROR")
        self._update_status("Error")
        messagebox.showerror("Workflow Error", error)
    
    def _stop(self) -> None:
        """실행 중지"""
        # TODO: 실제 중지 로직 구현
        self._log("중지 요청됨", "WARN")
        self._update_status("Stopping...")
    
    def _run_quick_task(self) -> None:
        """빠른 태스크 실행"""
        task = self.task_entry.get().strip()
        if not task:
            return
        
        self.task_entry.delete(0, tk.END)
        self._log(f"태스크 실행: {task}")
        
        thread = Thread(target=self._execute_task, args=(task,), daemon=True)
        thread.start()
    
    def _execute_task(self, task: str) -> None:
        """태스크 실행 (별도 스레드)"""
        result = self.orchestrator.auto_delegate(task)
        
        if result and result.success:
            self.root.after(0, lambda: self._log(f"결과: {result.output[:200]}...", "INFO"))
        elif result:
            self.root.after(0, lambda: self._log(f"오류: {result.error}", "ERROR"))
        else:
            self.root.after(0, lambda: self._log("적합한 에이전트를 찾을 수 없음", "WARN"))
    
    def _approve(self) -> None:
        """체크포인트 승인"""
        if self.engine and hasattr(self.engine, 'checkpoint_manager'):
            state = self.engine.checkpoint_manager.approve_current()
            if state:
                self._log(f"승인됨: {state.workflow_name}", "INFO")
                self._refresh_approvals()
            else:
                messagebox.showinfo("Info", "승인 대기 중인 요청이 없습니다")
    
    def _reject(self) -> None:
        """체크포인트 거부"""
        if self.engine and hasattr(self.engine, 'checkpoint_manager'):
            reason = tk.simpledialog.askstring("Reject", "거부 사유:")
            state = self.engine.checkpoint_manager.reject_current(reason or "사용자 거부")
            if state:
                self._log(f"거부됨: {state.workflow_name}", "WARN")
                self._refresh_approvals()
    
    def _refresh_lists(self) -> None:
        """목록 새로고침"""
        # 워크플로우 목록
        self.workflow_list.delete(0, tk.END)
        if self.engine:
            for wf in self.engine.list_workflows():
                self.workflow_list.insert(tk.END, wf['name'])
        
        # 에이전트 목록
        self.agent_list.delete(0, tk.END)
        for agent in self.orchestrator.list_agents():
            self.agent_list.insert(tk.END, agent['name'])
        
        self._refresh_approvals()
    
    def _refresh_approvals(self) -> None:
        """승인 대기 목록 새로고침"""
        self.approval_list.delete(0, tk.END)
        if self.engine and hasattr(self.engine, 'checkpoint_manager'):
            for name in self.engine.checkpoint_manager.list_pending():
                self.approval_list.insert(tk.END, name)
    
    def _load_workflow_file(self) -> None:
        """워크플로우 파일 로드"""
        if not self.engine:
            messagebox.showerror("Error", "WorkflowEngine이 설정되지 않았습니다")
            return
        
        file_path = filedialog.askopenfilename(
            filetypes=[("YAML files", "*.yaml *.yml"), ("JSON files", "*.json")]
        )
        if file_path:
            try:
                count = self.engine.load_from_file(file_path)
                self._log(f"로드됨: {count}개 워크플로우", "INFO")
                self._refresh_lists()
            except Exception as e:
                messagebox.showerror("Error", str(e))
    
    def run(self) -> None:
        """GUI 실행"""
        self.root.mainloop()


def run_gui(orchestrator: 'Orchestrator', **kwargs) -> None:
    """GUI 실행 헬퍼 함수"""
    gui = WorkflowGUI(orchestrator, **kwargs)
    gui.run()
