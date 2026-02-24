"""
파이프라인 모니터

LangGraph 노드 실행을 추적하고 성능 분석을 제공합니다.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from functools import wraps
import json

logger = logging.getLogger(__name__)


@dataclass
class NodeExecution:
    """
    노드 실행 기록
    
    각 노드의 실행 시간, 입출력 상태, 에러를 기록합니다.
    """
    node_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    input_keys: List[str] = field(default_factory=list)
    output_keys: List[str] = field(default_factory=list)
    input_snapshot: Dict = field(default_factory=dict)
    output_snapshot: Dict = field(default_factory=dict)
    error: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
    
    @property
    def duration_ms(self) -> float:
        """실행 시간 (밀리초)"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return 0
    
    @property
    def success(self) -> bool:
        """성공 여부"""
        return self.error is None
    
    def to_dict(self) -> dict:
        return {
            "node_name": self.node_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "input_keys": self.input_keys,
            "output_keys": self.output_keys,
            "error": self.error,
            "metadata": self.metadata,
        }


class PipelineMonitor:
    """
    파이프라인 실행 모니터
    
    사용법:
        monitor = PipelineMonitor()
        
        @monitor.trace("Parser")
        def parser_node(state):
            # ...
            return result
        
        # 실행 후
        monitor.print_summary()
        monitor.export_mermaid()
    """
    
    def __init__(self, verbose: bool = True, snapshot_limit: int = 200):
        """
        Args:
            verbose: 실시간 로그 출력 여부
            snapshot_limit: State 스냅샷 문자열 최대 길이
        """
        self.executions: List[NodeExecution] = []
        self.verbose = verbose
        self.snapshot_limit = snapshot_limit
        self._current: Optional[NodeExecution] = None
        self._start_time: Optional[datetime] = None
    
    def trace(self, node_name: str, **metadata):
        """
        노드 추적 데코레이터
        
        사용법:
            @monitor.trace("Parser")
            def parser_node(state):
                return result
        """
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(state: Dict, *args, **kwargs):
                self._on_node_start(node_name, state, metadata)
                try:
                    result = func(state, *args, **kwargs)
                    self._on_node_end(node_name, state, result)
                    return result
                except Exception as e:
                    self._on_node_error(node_name, e)
                    raise
            return wrapper
        return decorator
    
    def _on_node_start(self, node_name: str, state: Dict, metadata: Dict = None):
        """노드 시작"""
        if self._start_time is None:
            self._start_time = datetime.now()
        
        self._current = NodeExecution(
            node_name=node_name,
            start_time=datetime.now(),
            input_keys=list(state.keys()),
            input_snapshot=self._snapshot(state),
            metadata=metadata or {},
        )
        
        if self.verbose:
            logger.info(f"▶ [{node_name}] 시작")
    
    def _on_node_end(self, node_name: str, state: Dict, result: Dict):
        """노드 종료"""
        if self._current:
            self._current.end_time = datetime.now()
            self._current.output_keys = list(result.keys()) if result else []
            self._current.output_snapshot = self._snapshot(result) if result else {}
            self.executions.append(self._current)
            
            if self.verbose:
                logger.info(
                    f"✓ [{node_name}] 완료 ({self._current.duration_ms:.1f}ms)"
                )
            
            self._current = None
    
    def _on_node_error(self, node_name: str, error: Exception):
        """노드 에러"""
        if self._current:
            self._current.end_time = datetime.now()
            self._current.error = str(error)
            self.executions.append(self._current)
            
            if self.verbose:
                logger.error(f"✗ [{node_name}] 에러: {error}")
            
            self._current = None
    
    def _snapshot(self, data: Dict) -> Dict:
        """State 스냅샷 (큰 데이터 축약)"""
        if not data:
            return {}
        
        snapshot = {}
        for k, v in data.items():
            if isinstance(v, str) and len(v) > self.snapshot_limit:
                snapshot[k] = f"{v[:100]}... ({len(v)} chars)"
            elif isinstance(v, list):
                if len(v) > 5:
                    snapshot[k] = f"[{len(v)} items]"
                else:
                    snapshot[k] = v
            elif isinstance(v, dict):
                if len(str(v)) > self.snapshot_limit:
                    snapshot[k] = f"{{...}} ({len(v)} keys)"
                else:
                    snapshot[k] = v
            else:
                snapshot[k] = v
        return snapshot
    
    def print_summary(self):
        """실행 요약 출력"""
        print("\n" + "="*60)
        print("📊 Pipeline Execution Summary")
        print("="*60)
        
        if not self.executions:
            print("(실행 기록 없음)")
            return
        
        total_time = sum(e.duration_ms for e in self.executions)
        
        for i, ex in enumerate(self.executions, 1):
            status = "✓" if ex.success else "✗"
            bar_len = int(ex.duration_ms / total_time * 30) if total_time > 0 else 0
            bar = "█" * bar_len
            
            print(f"{status} {i}. {ex.node_name:20} {ex.duration_ms:8.1f}ms {bar}")
            
            if ex.error:
                print(f"   └─ Error: {ex.error}")
        
        print("-"*60)
        print(f"Total: {total_time:.1f}ms ({len(self.executions)} nodes)")
        
        if self._start_time:
            wall_time = (datetime.now() - self._start_time).total_seconds() * 1000
            print(f"Wall time: {wall_time:.1f}ms")
    
    def export_mermaid(self) -> str:
        """Mermaid 다이어그램 생성"""
        if not self.executions:
            return "graph LR\n    A[No executions]"
        
        lines = ["graph LR"]
        
        for i, ex in enumerate(self.executions):
            node_id = f"N{i}"
            label = f"{ex.node_name}<br/>{ex.duration_ms:.0f}ms"
            
            if ex.error:
                lines.append(f'    {node_id}["{label}"]:::error')
            else:
                lines.append(f'    {node_id}["{label}"]:::success')
            
            if i > 0:
                lines.append(f"    N{i-1} --> {node_id}")
        
        lines.append("    classDef success fill:#90EE90,stroke:#228B22")
        lines.append("    classDef error fill:#FFB6C1,stroke:#DC143C")
        
        return "\n".join(lines)
    
    def export_json(self, filepath: str = None) -> str:
        """JSON 형식으로 내보내기"""
        data = {
            "start_time": self._start_time.isoformat() if self._start_time else None,
            "total_nodes": len(self.executions),
            "total_duration_ms": sum(e.duration_ms for e in self.executions),
            "success": all(e.success for e in self.executions),
            "executions": [e.to_dict() for e in self.executions],
        }
        
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        
        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(json_str)
        
        return json_str
    
    def export_html_report(self, filepath: str = None) -> str:
        """HTML 리포트 생성"""
        mermaid = self.export_mermaid()
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Pipeline Execution Report</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 20px; }}
        h1 {{ color: #333; }}
        .summary {{ background: #f5f5f5; padding: 15px; border-radius: 8px; }}
        .node-table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        .node-table th, .node-table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        .node-table th {{ background: #4CAF50; color: white; }}
        .success {{ color: green; }}
        .error {{ color: red; }}
        .mermaid {{ margin-top: 20px; }}
    </style>
</head>
<body>
    <h1>📊 Pipeline Execution Report</h1>
    
    <div class="summary">
        <p><strong>Total Duration:</strong> {sum(e.duration_ms for e in self.executions):.1f}ms</p>
        <p><strong>Nodes Executed:</strong> {len(self.executions)}</p>
        <p><strong>Status:</strong> {'✓ Success' if all(e.success for e in self.executions) else '✗ Failed'}</p>
    </div>
    
    <h2>Execution Flow</h2>
    <div class="mermaid">
{mermaid}
    </div>
    
    <h2>Node Details</h2>
    <table class="node-table">
        <tr>
            <th>#</th>
            <th>Node</th>
            <th>Duration</th>
            <th>Status</th>
            <th>Input Keys</th>
            <th>Output Keys</th>
        </tr>
"""
        
        for i, ex in enumerate(self.executions, 1):
            status_class = "success" if ex.success else "error"
            status_text = "✓" if ex.success else f"✗ {ex.error}"
            html += f"""        <tr>
            <td>{i}</td>
            <td>{ex.node_name}</td>
            <td>{ex.duration_ms:.1f}ms</td>
            <td class="{status_class}">{status_text}</td>
            <td>{', '.join(ex.input_keys)}</td>
            <td>{', '.join(ex.output_keys)}</td>
        </tr>
"""
        
        html += """    </table>
    
    <script>mermaid.initialize({startOnLoad:true});</script>
</body>
</html>"""
        
        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html)
        
        return html
    
    def get_timeline(self) -> List[dict]:
        """시각화용 타임라인 데이터"""
        return [e.to_dict() for e in self.executions]
    
    def clear(self):
        """기록 초기화"""
        self.executions = []
        self._current = None
        self._start_time = None
