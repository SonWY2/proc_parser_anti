"""
Tkinter GUI 메인 애플리케이션

Pro*C to MyBatis SQL 변환 검증 도구의 GUI입니다.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
from typing import Optional, List, Dict, Any
from loguru import logger

from .yaml_loader import load_yaml
from .static_analyzer import StaticAnalyzer, CheckStatus, AnalysisResult
from .diff_highlighter import DiffHighlighter
from .llm_client import LLMClient
from .prompt import DEFAULT_PROMPT
from .exporter import export_approved, export_rejected, export_all_with_status, generate_export_filename
from .session import SessionData, save_session, load_session, generate_session_filename
import yaml


class SQLValidatorApp:
    """SQL 변환 검증 GUI 애플리케이션"""
    
    # 색상 테마
    COLORS = {
        'replace': '#fff3cd',    # 노란색 (변경)
        'delete': '#f8d7da',     # 빨간색 (삭제)
        'insert': '#d4edda',     # 초록색 (추가)
        'pass': '#28a745',       # 통과
        'fail': '#dc3545',       # 실패
        'warning': '#ffc107',    # 경고
        'info': '#17a2b8',       # 정보
        'approved': '#d4edda',   # 승인 배경
        'rejected': '#f8d7da',   # 거부 배경
    }
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Pro*C to MyBatis SQL Validator")
        self.root.geometry("1400x900")
        
        # 상태 변수
        self.sql_items: List[Dict[str, Any]] = []
        self.current_index = 0
        self.current_prompt = DEFAULT_PROMPT
        self.yaml_path: str = ""
        
        # 검증 상태: {index: 'approved' | 'rejected'}
        self.validation_statuses: Dict[int, str] = {}
        # 코멘트: {index: comment_text}
        self.comments: Dict[int, str] = {}
        # 분석 결과 캐시: {index: AnalysisResult}
        self.analysis_results: Dict[int, AnalysisResult] = {}
        
        # 컴포넌트
        self.analyzer = StaticAnalyzer()
        self.diff_highlighter = DiffHighlighter(ignore_whitespace=True)
        self.llm_client = LLMClient()
        
        # UI 구성
        self._setup_ui()
        self._setup_tags()
        self._setup_keyboard_shortcuts()
        
        logger.info("SQLValidatorApp 시작됨")
    
    def _setup_ui(self):
        """UI 레이아웃 구성"""
        # 메인 프레임
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 상단: 파일 선택 및 네비게이션
        self._setup_toolbar(main_frame)
        
        # 중앙: A/B 뷰 + 승인/거부 버튼
        self._setup_diff_view(main_frame)
        
        # 하단: 분석 결과
        self._setup_analysis_panel(main_frame)
    
    def _setup_toolbar(self, parent):
        """상단 툴바 구성"""
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, pady=(0, 10))
        
        # 파일 선택
        ttk.Button(toolbar, text="📂 YAML 열기", command=self._open_yaml).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="📋 YAML 붙여넣기", command=self._paste_yaml).pack(side=tk.LEFT, padx=5)
        
        # 세션 관리
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        ttk.Button(toolbar, text="💾 세션 저장", command=self._save_session).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="📥 세션 로드", command=self._load_session).pack(side=tk.LEFT, padx=5)
        
        # 네비게이션
        nav_frame = ttk.Frame(toolbar)
        nav_frame.pack(side=tk.LEFT, padx=20)
        
        ttk.Button(nav_frame, text="◀ 이전", command=self._prev_item).pack(side=tk.LEFT, padx=2)
        self.nav_label = ttk.Label(nav_frame, text="0 / 0")
        self.nav_label.pack(side=tk.LEFT, padx=10)
        ttk.Button(nav_frame, text="다음 ▶", command=self._next_item).pack(side=tk.LEFT, padx=2)
        
        # 상태 표시
        self.status_label = ttk.Label(nav_frame, text="", font=('', 10, 'bold'))
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        # LLM 분석
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        ttk.Button(toolbar, text="🤖 LLM 분석", command=self._analyze_with_llm).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="⚙️ 프롬프트 설정", command=self._open_prompt_editor).pack(side=tk.LEFT, padx=5)
        
        # 내보내기
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        ttk.Button(toolbar, text="✅ 승인 내보내기", command=self._export_approved).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="❌ 거부 내보내기", command=self._export_rejected).pack(side=tk.LEFT, padx=5)
        
        # API 상태
        self.api_status_label = ttk.Label(toolbar, text="")
        self.api_status_label.pack(side=tk.RIGHT, padx=10)
        self._update_api_status()
    
    def _setup_diff_view(self, parent):
        """A/B Side-by-Side diff 뷰 구성"""
        diff_frame = ttk.Frame(parent)
        diff_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 그리드 구성
        diff_frame.columnconfigure(0, weight=1)
        diff_frame.columnconfigure(1, weight=1)
        diff_frame.rowconfigure(1, weight=1)
        
        # 헤더
        ttk.Label(diff_frame, text="🔵 원본 (Pro*C SQL)", font=('', 12, 'bold')).grid(row=0, column=0, sticky='w', padx=5)
        ttk.Label(diff_frame, text="🟢 변환 결과 (MyBatis SQL)", font=('', 12, 'bold')).grid(row=0, column=1, sticky='w', padx=5)
        
        # 텍스트 영역
        self.asis_text = scrolledtext.ScrolledText(diff_frame, wrap=tk.WORD, font=('Consolas', 11))
        self.asis_text.grid(row=1, column=0, sticky='nsew', padx=(5, 2), pady=5)
        
        self.tobe_text = scrolledtext.ScrolledText(diff_frame, wrap=tk.WORD, font=('Consolas', 11))
        self.tobe_text.grid(row=1, column=1, sticky='nsew', padx=(2, 5), pady=5)
        
        # 읽기 전용
        self.asis_text.config(state=tk.DISABLED)
        self.tobe_text.config(state=tk.DISABLED)
        
        # 승인/거부 버튼 + 코멘트 영역
        action_frame = ttk.Frame(diff_frame)
        action_frame.grid(row=2, column=0, columnspan=2, sticky='ew', pady=5, padx=5)
        
        # 승인/거부 버튼
        btn_frame = ttk.Frame(action_frame)
        btn_frame.pack(side=tk.LEFT)
        
        self.approve_btn = ttk.Button(btn_frame, text="✅ 승인 (A)", command=self._approve_current)
        self.approve_btn.pack(side=tk.LEFT, padx=5)
        
        self.reject_btn = ttk.Button(btn_frame, text="❌ 거부 (R)", command=self._reject_current)
        self.reject_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="⬜ 초기화", command=self._clear_status).pack(side=tk.LEFT, padx=5)
        
        # 코멘트 입력
        ttk.Label(action_frame, text="💬 코멘트:").pack(side=tk.LEFT, padx=(20, 5))
        self.comment_entry = ttk.Entry(action_frame, width=60)
        self.comment_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.comment_entry.bind('<Return>', lambda e: self._save_comment())
        self.comment_entry.bind('<FocusOut>', lambda e: self._save_comment())
    
    def _setup_analysis_panel(self, parent):
        """하단 분석 결과 패널 구성"""
        # 노트북 (탭)
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # 정적 분석 탭
        static_frame = ttk.Frame(notebook, padding="10")
        notebook.add(static_frame, text="📊 정적 분석")
        
        self.static_result_text = scrolledtext.ScrolledText(static_frame, height=8, font=('', 10))
        self.static_result_text.pack(fill=tk.BOTH, expand=True)
        self.static_result_text.config(state=tk.DISABLED)
        
        # LLM 피드백 탭
        llm_frame = ttk.Frame(notebook, padding="10")
        notebook.add(llm_frame, text="🤖 LLM 피드백")
        
        self.llm_result_text = scrolledtext.ScrolledText(llm_frame, height=8, font=('', 10))
        self.llm_result_text.pack(fill=tk.BOTH, expand=True)
        self.llm_result_text.config(state=tk.DISABLED)
        
        # 대시보드 탭
        dashboard_frame = ttk.Frame(notebook, padding="10")
        notebook.add(dashboard_frame, text="📈 대시보드")
        
        self.dashboard_text = scrolledtext.ScrolledText(dashboard_frame, height=8, font=('', 10))
        self.dashboard_text.pack(fill=tk.BOTH, expand=True)
        self.dashboard_text.config(state=tk.DISABLED)
    
    def _setup_tags(self):
        """텍스트 위젯 태그 설정"""
        for widget in [self.asis_text, self.tobe_text]:
            widget.tag_configure('replace', background=self.COLORS['replace'])
            widget.tag_configure('delete', background=self.COLORS['delete'])
            widget.tag_configure('insert', background=self.COLORS['insert'])
    
    def _setup_keyboard_shortcuts(self):
        """키보드 단축키 설정"""
        self.root.bind('<Left>', lambda e: self._prev_item())
        self.root.bind('<Right>', lambda e: self._next_item())
        self.root.bind('a', lambda e: self._approve_current())
        self.root.bind('A', lambda e: self._approve_current())
        self.root.bind('r', lambda e: self._reject_current())
        self.root.bind('R', lambda e: self._reject_current())
        self.root.bind('<Control-o>', lambda e: self._open_yaml())
        self.root.bind('<Control-s>', lambda e: self._save_session())
        self.root.bind('<Control-e>', lambda e: self._export_approved())
    
    def _update_api_status(self):
        """API 연결 상태 업데이트"""
        if self.llm_client.is_configured:
            if self.llm_client.is_available:
                self.api_status_label.config(text="🟢 API 연결됨", foreground="green")
            else:
                self.api_status_label.config(text="🔴 API 연결 실패", foreground="red")
        else:
            self.api_status_label.config(text="⚫ API 미설정", foreground="gray")
    
    def _open_yaml(self):
        """YAML 파일 열기"""
        file_path = filedialog.askopenfilename(
            title="YAML 파일 선택",
            filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            self.sql_items = load_yaml(file_path)
            self.yaml_path = file_path
            self.current_index = 0
            self.validation_statuses.clear()
            self.comments.clear()
            self.analysis_results.clear()
            
            if self.sql_items:
                self._display_current_item()
                self._update_dashboard()
                messagebox.showinfo("로드 완료", f"{len(self.sql_items)}개 SQL 항목을 로드했습니다.")
            else:
                messagebox.showwarning("경고", "유효한 SQL 항목이 없습니다.")
                
        except Exception as e:
            logger.error(f"YAML 로드 실패: {e}")
            messagebox.showerror("오류", f"파일 로드 실패:\n{str(e)}")
    
    def _display_current_item(self):
        """현재 SQL 항목 표시"""
        if not self.sql_items:
            return
        
        item = self.sql_items[self.current_index]
        asis = item['sql']
        tobe = item['parsed_sql']
        
        # 네비게이션 레이블 업데이트
        self.nav_label.config(text=f"{self.current_index + 1} / {len(self.sql_items)}")
        
        # 상태 표시 업데이트
        self._update_status_display()
        
        # 텍스트 표시
        self._set_text(self.asis_text, asis)
        self._set_text(self.tobe_text, tobe)
        
        # 하이라이트 적용
        self._apply_highlights(asis, tobe)
        
        # 정적 분석 실행
        self._run_static_analysis(asis, tobe)
        
        # 코멘트 로드
        comment = self.comments.get(self.current_index, "")
        self.comment_entry.delete(0, tk.END)
        self.comment_entry.insert(0, comment)
        
        # LLM 결과 초기화
        self._set_text(self.llm_result_text, "LLM 분석 버튼을 클릭하여 분석을 시작하세요.")
    
    def _update_status_display(self):
        """현재 항목의 상태 표시 업데이트"""
        status = self.validation_statuses.get(self.current_index)
        if status == 'approved':
            self.status_label.config(text="✅ 승인됨", foreground="green")
        elif status == 'rejected':
            self.status_label.config(text="❌ 거부됨", foreground="red")
        else:
            self.status_label.config(text="⬜ 미검토", foreground="gray")
    
    def _set_text(self, widget, text: str):
        """텍스트 위젯에 텍스트 설정"""
        widget.config(state=tk.NORMAL)
        widget.delete(1.0, tk.END)
        widget.insert(tk.END, text)
        widget.config(state=tk.DISABLED)
    
    def _apply_highlights(self, asis: str, tobe: str):
        """diff 하이라이트 적용"""
        highlights = self.diff_highlighter.get_highlight_ranges(asis, tobe)
        
        # 기존 태그 제거
        for widget in [self.asis_text, self.tobe_text]:
            widget.config(state=tk.NORMAL)
            for tag in ['replace', 'delete', 'insert']:
                widget.tag_remove(tag, 1.0, tk.END)
        
        # asis 하이라이트
        for start, end, tag in highlights['asis']:
            self.asis_text.tag_add(tag, f"1.0+{start}c", f"1.0+{end}c")
        
        # tobe 하이라이트
        for start, end, tag in highlights['tobe']:
            self.tobe_text.tag_add(tag, f"1.0+{start}c", f"1.0+{end}c")
        
        # 읽기 전용으로 복원
        self.asis_text.config(state=tk.DISABLED)
        self.tobe_text.config(state=tk.DISABLED)
    
    def _run_static_analysis(self, asis: str, tobe: str):
        """정적 분석 실행 및 결과 표시"""
        result = self.analyzer.analyze(asis, tobe)
        
        # 캐시에 저장
        self.analysis_results[self.current_index] = result
        
        lines = []
        for check in result.checks:
            if check.status == CheckStatus.PASS:
                icon = "✅"
            elif check.status == CheckStatus.FAIL:
                icon = "❌"
            elif check.status == CheckStatus.WARNING:
                icon = "⚠️"
            else:
                icon = "ℹ️"
            
            lines.append(f"{icon} [{check.name}] {check.message}")
            if check.details:
                lines.append(f"   └─ {check.details}")
        
        # 요약
        summary = f"\n📊 결과: {result.pass_count} 통과, {result.fail_count} 실패, {result.warning_count} 경고"
        lines.append(summary)
        
        # 유사도
        similarity = self.diff_highlighter.get_similarity_ratio(asis, tobe)
        lines.append(f"📏 유사도: {similarity:.1%}")
        
        self._set_text(self.static_result_text, '\n'.join(lines))
    
    def _prev_item(self):
        """이전 항목으로 이동"""
        if self.sql_items and self.current_index > 0:
            self._save_comment()
            self.current_index -= 1
            self._display_current_item()
    
    def _next_item(self):
        """다음 항목으로 이동"""
        if self.sql_items and self.current_index < len(self.sql_items) - 1:
            self._save_comment()
            self.current_index += 1
            self._display_current_item()
    
    def _approve_current(self):
        """현재 항목 승인"""
        if not self.sql_items:
            return
        self.validation_statuses[self.current_index] = 'approved'
        self._update_status_display()
        self._update_dashboard()
        logger.info(f"항목 {self.current_index + 1} 승인됨")
    
    def _reject_current(self):
        """현재 항목 거부"""
        if not self.sql_items:
            return
        self.validation_statuses[self.current_index] = 'rejected'
        self._update_status_display()
        self._update_dashboard()
        logger.info(f"항목 {self.current_index + 1} 거부됨")
    
    def _clear_status(self):
        """현재 항목 상태 초기화"""
        if not self.sql_items:
            return
        if self.current_index in self.validation_statuses:
            del self.validation_statuses[self.current_index]
        self._update_status_display()
        self._update_dashboard()
    
    def _save_comment(self):
        """현재 코멘트 저장"""
        if not self.sql_items:
            return
        comment = self.comment_entry.get().strip()
        if comment:
            self.comments[self.current_index] = comment
        elif self.current_index in self.comments:
            del self.comments[self.current_index]
    
    def _update_dashboard(self):
        """대시보드 업데이트"""
        if not self.sql_items:
            self._set_text(self.dashboard_text, "YAML 파일을 로드하세요.")
            return
        
        total = len(self.sql_items)
        approved = sum(1 for s in self.validation_statuses.values() if s == 'approved')
        rejected = sum(1 for s in self.validation_statuses.values() if s == 'rejected')
        pending = total - approved - rejected
        
        lines = [
            "=" * 50,
            "📊 검증 현황 대시보드",
            "=" * 50,
            "",
            f"📁 전체 항목: {total}개",
            f"✅ 승인: {approved}개 ({approved/total*100:.1f}%)" if total > 0 else "✅ 승인: 0개",
            f"❌ 거부: {rejected}개 ({rejected/total*100:.1f}%)" if total > 0 else "❌ 거부: 0개",
            f"⬜ 미검토: {pending}개 ({pending/total*100:.1f}%)" if total > 0 else "⬜ 미검토: 0개",
            "",
        ]
        
        # 진행률 바
        if total > 0:
            reviewed = approved + rejected
            progress = reviewed / total
            bar_len = 40
            filled = int(bar_len * progress)
            bar = "█" * filled + "░" * (bar_len - filled)
            lines.append(f"진행률: [{bar}] {progress*100:.1f}%")
        
        # 정적 분석 통계
        if self.analysis_results:
            lines.append("")
            lines.append("-" * 50)
            lines.append("📈 정적 분석 통계")
            lines.append("-" * 50)
            
            total_pass = sum(r.pass_count for r in self.analysis_results.values())
            total_fail = sum(r.fail_count for r in self.analysis_results.values())
            total_warn = sum(r.warning_count for r in self.analysis_results.values())
            
            lines.append(f"✅ 총 통과: {total_pass}")
            lines.append(f"❌ 총 실패: {total_fail}")
            lines.append(f"⚠️ 총 경고: {total_warn}")
        
        # 단축키 안내
        lines.extend([
            "",
            "-" * 50,
            "⌨️ 키보드 단축키",
            "-" * 50,
            "← / → : 이전/다음 항목",
            "A : 승인",
            "R : 거부",
            "Ctrl+O : YAML 열기",
            "Ctrl+S : 세션 저장",
            "Ctrl+E : 승인 내보내기",
        ])
        
        self._set_text(self.dashboard_text, '\n'.join(lines))
    
    def _analyze_with_llm(self):
        """LLM으로 분석 실행"""
        if not self.sql_items:
            messagebox.showwarning("경고", "먼저 YAML 파일을 로드하세요.")
            return
        
        if not self.llm_client.is_configured:
            messagebox.showwarning("경고", ".env 파일에 VLLM_API_ENDPOINT를 설정하세요.")
            return
        
        item = self.sql_items[self.current_index]
        asis = item['sql']
        tobe = item['parsed_sql']
        
        # 분석 중 표시
        self._set_text(self.llm_result_text, "🔄 LLM 분석 중...")
        self.root.update()
        
        # API 호출
        result = self.llm_client.analyze_conversion(asis, tobe, self.current_prompt)
        
        if result['success']:
            self._set_text(self.llm_result_text, result['response'])
        else:
            self._set_text(self.llm_result_text, f"❌ 오류: {result['error']}")
    
    def _open_prompt_editor(self):
        """프롬프트 편집 창 열기"""
        editor = PromptEditorWindow(self.root, self.current_prompt)
        self.root.wait_window(editor.window)
        
        if editor.result:
            self.current_prompt = editor.result
            logger.info("프롬프트 업데이트됨")
    
    def _paste_yaml(self):
        """YAML 텍스트 붙여넣기 창 열기"""
        paste_window = YamlPasteWindow(self.root)
        self.root.wait_window(paste_window.window)
        
        if paste_window.result:
            self.sql_items = paste_window.result
            self.yaml_path = ""
            self.current_index = 0
            self.validation_statuses.clear()
            self.comments.clear()
            self.analysis_results.clear()
            
            if self.sql_items:
                self._display_current_item()
                self._update_dashboard()
                messagebox.showinfo("로드 완료", f"{len(self.sql_items)}개 SQL 항목을 로드했습니다.")
            else:
                messagebox.showwarning("경고", "유효한 SQL 항목이 없습니다.")
    
    def _export_approved(self):
        """승인된 항목 내보내기"""
        if not self.sql_items:
            messagebox.showwarning("경고", "먼저 YAML 파일을 로드하세요.")
            return
        
        approved_count = sum(1 for s in self.validation_statuses.values() if s == 'approved')
        if approved_count == 0:
            messagebox.showwarning("경고", "승인된 항목이 없습니다.")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="승인 항목 저장",
            defaultextension=".yaml",
            initialfile=generate_export_filename("approved"),
            filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")]
        )
        
        if file_path:
            count = export_approved(self.sql_items, self.validation_statuses, file_path)
            messagebox.showinfo("내보내기 완료", f"{count}개 승인 항목을 저장했습니다.")
    
    def _export_rejected(self):
        """거부된 항목 내보내기"""
        if not self.sql_items:
            messagebox.showwarning("경고", "먼저 YAML 파일을 로드하세요.")
            return
        
        rejected_count = sum(1 for s in self.validation_statuses.values() if s == 'rejected')
        if rejected_count == 0:
            messagebox.showwarning("경고", "거부된 항목이 없습니다.")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="거부 항목 저장",
            defaultextension=".yaml",
            initialfile=generate_export_filename("rejected"),
            filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")]
        )
        
        if file_path:
            count = export_rejected(self.sql_items, self.validation_statuses, file_path)
            messagebox.showinfo("내보내기 완료", f"{count}개 거부 항목을 저장했습니다.")
    
    def _save_session(self):
        """세션 저장"""
        if not self.sql_items:
            messagebox.showwarning("경고", "저장할 세션이 없습니다.")
            return
        
        self._save_comment()  # 현재 코멘트 저장
        
        file_path = filedialog.asksaveasfilename(
            title="세션 저장",
            defaultextension=".json",
            initialfile=generate_session_filename(),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if file_path:
            session = SessionData(
                yaml_path=self.yaml_path,
                current_index=self.current_index,
                validation_statuses=self.validation_statuses.copy(),
                comments=self.comments.copy(),
                custom_prompt=self.current_prompt
            )
            
            if save_session(session, file_path):
                messagebox.showinfo("저장 완료", "세션이 저장되었습니다.")
            else:
                messagebox.showerror("오류", "세션 저장에 실패했습니다.")
    
    def _load_session(self):
        """세션 로드"""
        file_path = filedialog.askopenfilename(
            title="세션 파일 선택",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
        
        session = load_session(file_path)
        if not session:
            messagebox.showerror("오류", "세션 로드에 실패했습니다.")
            return
        
        # YAML 파일 로드
        if session.yaml_path and Path(session.yaml_path).exists():
            try:
                self.sql_items = load_yaml(session.yaml_path)
                self.yaml_path = session.yaml_path
            except Exception as e:
                messagebox.showerror("오류", f"YAML 파일 로드 실패: {e}")
                return
        else:
            messagebox.showwarning("경고", "원본 YAML 파일을 찾을 수 없습니다. YAML을 다시 로드해주세요.")
            self.sql_items = []
        
        # 상태 복원
        self.current_index = session.current_index
        self.validation_statuses = session.validation_statuses
        self.comments = session.comments
        self.current_prompt = session.custom_prompt if session.custom_prompt else DEFAULT_PROMPT
        self.analysis_results.clear()
        
        if self.sql_items:
            self._display_current_item()
            self._update_dashboard()
            messagebox.showinfo("로드 완료", f"세션이 복원되었습니다. (항목: {len(self.sql_items)}개)")


class PromptEditorWindow:
    """프롬프트 편집 창"""
    
    def __init__(self, parent, initial_prompt: str):
        self.result: Optional[str] = None
        
        self.window = tk.Toplevel(parent)
        self.window.title("프롬프트 설정")
        self.window.geometry("800x600")
        self.window.transient(parent)
        self.window.grab_set()
        
        # 안내
        ttk.Label(
            self.window, 
            text="LLM에 전달할 프롬프트를 편집합니다. {asis}와 {tobe} 플레이스홀더가 필요합니다.",
            wraplength=780
        ).pack(pady=10, padx=10)
        
        # 텍스트 편집기
        self.text = scrolledtext.ScrolledText(self.window, font=('Consolas', 10))
        self.text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.text.insert(tk.END, initial_prompt)
        
        # 버튼
        btn_frame = ttk.Frame(self.window)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="기본값 복원", command=self._restore_default).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="취소", command=self.window.destroy).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="저장", command=self._save).pack(side=tk.LEFT, padx=5)
    
    def _restore_default(self):
        """기본 프롬프트 복원"""
        self.text.delete(1.0, tk.END)
        self.text.insert(tk.END, DEFAULT_PROMPT)
    
    def _save(self):
        """프롬프트 저장"""
        prompt = self.text.get(1.0, tk.END).strip()
        
        if '{asis}' not in prompt or '{tobe}' not in prompt:
            messagebox.showerror("오류", "{asis}와 {tobe} 플레이스홀더가 필요합니다.")
            return
        
        self.result = prompt
        self.window.destroy()


class YamlPasteWindow:
    """YAML 텍스트 붙여넣기 창"""
    
    SAMPLE_YAML = '''# 예시 형식
- sql: |
    EXEC SQL SELECT emp_id, emp_name
    INTO :emp_id, :emp_name
    FROM employees
    WHERE dept_id = :dept_id;
  parsed_sql: |
    SELECT emp_id, emp_name
    FROM employees
    WHERE dept_id = #{deptId}
'''
    
    def __init__(self, parent):
        self.result: Optional[List[Dict[str, Any]]] = None
        
        self.window = tk.Toplevel(parent)
        self.window.title("YAML 붙여넣기")
        self.window.geometry("900x700")
        self.window.transient(parent)
        self.window.grab_set()
        
        # 안내
        ttk.Label(
            self.window, 
            text="YAML 형식으로 SQL 데이터를 붙여넣으세요. 'sql'과 'parsed_sql' 키가 필요합니다.",
            wraplength=880
        ).pack(pady=10, padx=10)
        
        # 텍스트 편집기
        self.text = scrolledtext.ScrolledText(self.window, font=('Consolas', 10))
        self.text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 버튼
        btn_frame = ttk.Frame(self.window)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="예시 보기", command=self._show_sample).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="클립보드에서 붙여넣기", command=self._paste_from_clipboard).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="취소", command=self.window.destroy).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="로드", command=self._load).pack(side=tk.LEFT, padx=5)
    
    def _show_sample(self):
        """예시 YAML 표시"""
        self.text.delete(1.0, tk.END)
        self.text.insert(tk.END, self.SAMPLE_YAML)
    
    def _paste_from_clipboard(self):
        """클립보드에서 붙여넣기"""
        try:
            clipboard_text = self.window.clipboard_get()
            self.text.delete(1.0, tk.END)
            self.text.insert(tk.END, clipboard_text)
        except tk.TclError:
            messagebox.showwarning("경고", "클립보드가 비어있습니다.")
    
    def _load(self):
        """YAML 로드"""
        yaml_text = self.text.get(1.0, tk.END).strip()
        
        if not yaml_text:
            messagebox.showwarning("경고", "YAML 내용을 입력하세요.")
            return
        
        try:
            data = yaml.safe_load(yaml_text)
            
            if data is None:
                messagebox.showwarning("경고", "빈 YAML입니다.")
                return
            
            if isinstance(data, dict):
                data = [data]
            
            if not isinstance(data, list):
                messagebox.showerror("오류", "YAML 형식이 올바르지 않습니다. 리스트 또는 딕셔너리가 필요합니다.")
                return
            
            validated_items = []
            for i, item in enumerate(data):
                if not isinstance(item, dict):
                    continue
                if 'sql' not in item or 'parsed_sql' not in item:
                    continue
                
                validated_items.append({
                    'sql': str(item['sql']).strip(),
                    'parsed_sql': str(item['parsed_sql']).strip(),
                    'index': i,
                    'metadata': {k: v for k, v in item.items() if k not in ('sql', 'parsed_sql')}
                })
            
            if not validated_items:
                messagebox.showwarning("경고", "유효한 SQL 항목이 없습니다. 'sql'과 'parsed_sql' 키가 필요합니다.")
                return
            
            self.result = validated_items
            self.window.destroy()
            
        except yaml.YAMLError as e:
            messagebox.showerror("오류", f"YAML 파싱 오류:\n{str(e)}")


def main():
    """애플리케이션 실행"""
    # 로거 설정
    logger.add(
        "sql_validator.log",
        rotation="10 MB",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
    )
    
    root = tk.Tk()
    app = SQLValidatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
