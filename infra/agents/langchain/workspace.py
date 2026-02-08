"""
에이전트 워크스페이스

서브에이전트 간 파일 기반 통신을 위한 공유 워크스페이스입니다.
각 에이전트는 이 워크스페이스에 파일을 읽고/쓰면서 데이터를 교환합니다.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class AgentMessage:
    """에이전트 간 메시지"""
    timestamp: str
    from_agent: str
    to_agent: str
    message_type: str  # "request", "response", "data", "error"
    content: Dict[str, Any]
    file_refs: List[str] = field(default_factory=list)  # 참조된 파일들
    
    def to_dict(self) -> dict:
        return asdict(self)


class AgentWorkspace:
    """
    에이전트 공유 워크스페이스
    
    파일 구조:
        workspace_dir/
        ├── messages/           # 에이전트 간 메시지 로그
        │   ├── Orchestrator_to_Parser_001.json
        │   └── Parser_to_Orchestrator_002.json
        ├── data/               # 공유 데이터 파일
        │   ├── source_code.pc
        │   ├── ast_data.json
        │   └── metadata.json
        └── artifacts/          # 생성된 아티팩트
            ├── java_code.java
            └── mapper.xml
    
    사용법:
        workspace = AgentWorkspace("./agent_workspace")
        
        # 데이터 저장
        workspace.save_data("ast_data", ast_dict, from_agent="Parser")
        
        # 데이터 로드
        ast = workspace.load_data("ast_data")
        
        # 메시지 전송
        workspace.send_message("Parser", "Critic", "data", {"status": "done"})
        
        # 메시지 히스토리 조회
        history = workspace.get_message_history()
    """
    
    def __init__(self, workspace_dir: str = "./agent_workspace"):
        self.workspace_dir = Path(workspace_dir)
        self._init_directories()
        self._message_counter = self._init_message_counter()  # 기존 파일에서 마지막 번호 읽기
        self._messages: List[AgentMessage] = []
    
    def _init_directories(self):
        """디렉토리 구조 초기화"""
        (self.workspace_dir / "messages").mkdir(parents=True, exist_ok=True)
        (self.workspace_dir / "data").mkdir(parents=True, exist_ok=True)
        (self.workspace_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        logger.debug(f"Workspace 초기화: {self.workspace_dir.absolute()}")
    
    def _init_message_counter(self) -> int:
        """
        기존 메시지 파일에서 마지막 카운터 값을 읽어옴
        파일명 형식: 0001_Agent_to_Agent.json
        """
        import re
        
        messages_dir = self.workspace_dir / "messages"
        if not messages_dir.exists():
            return 0
        
        max_counter = 0
        for filepath in messages_dir.iterdir():
            # 파일명에서 숫자 추출 (예: 0001_xxx.json -> 1)
            match = re.match(r'^(\d+)_', filepath.name)
            if match:
                counter = int(match.group(1))
                if counter > max_counter:
                    max_counter = counter
        
        return max_counter
    
    # ==========================================
    # 데이터 저장/로드
    # ==========================================
    
    def save_data(
        self, 
        name: str, 
        data: Any, 
        from_agent: str = "unknown",
        as_json: bool = True
    ) -> Path:
        """
        데이터 저장
        
        Args:
            name: 파일 이름 (확장자 제외)
            data: 저장할 데이터
            from_agent: 저장하는 에이전트 이름
            as_json: JSON으로 저장 여부
            
        Returns:
            저장된 파일 경로
        """
        if as_json:
            filepath = self.workspace_dir / "data" / f"{name}.json"
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        else:
            filepath = self.workspace_dir / "data" / name
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(str(data))
        
        logger.debug(f"[{from_agent}] 데이터 저장: {filepath.name}")
        return filepath
    
    def load_data(self, name: str, as_json: bool = True) -> Any:
        """
        데이터 로드
        
        Args:
            name: 파일 이름 (확장자 제외)
            as_json: JSON으로 파싱 여부
            
        Returns:
            로드된 데이터
        """
        if as_json:
            filepath = self.workspace_dir / "data" / f"{name}.json"
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            filepath = self.workspace_dir / "data" / name
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
    
    def save_source(self, filename: str, content: str) -> Path:
        """소스 파일 저장"""
        filepath = self.workspace_dir / "data" / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath
    
    def save_artifact(self, name: str, content: str, ext: str = "") -> Path:
        """아티팩트 저장"""
        filename = f"{name}{ext}" if ext else name
        filepath = self.workspace_dir / "artifacts" / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath
    
    def list_data_files(self) -> List[str]:
        """데이터 파일 목록"""
        return [f.name for f in (self.workspace_dir / "data").iterdir()]
    
    def list_artifacts(self) -> List[str]:
        """아티팩트 목록"""
        return [f.name for f in (self.workspace_dir / "artifacts").iterdir()]
    
    # ==========================================
    # 메시지 통신
    # ==========================================
    
    def send_message(
        self,
        from_agent: str,
        to_agent: str,
        message_type: str,
        content: Dict[str, Any],
        file_refs: List[str] = None,
        save_to_file: bool = True
    ) -> AgentMessage:
        """
        에이전트 간 메시지 전송
        
        Args:
            from_agent: 발신 에이전트
            to_agent: 수신 에이전트
            message_type: 메시지 유형 (request, response, data, error)
            content: 메시지 내용
            file_refs: 참조 파일 목록
            save_to_file: 파일로 저장 여부
            
        Returns:
            생성된 메시지 객체
        """
        self._message_counter += 1
        
        message = AgentMessage(
            timestamp=datetime.now().isoformat(),
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            content=content,
            file_refs=file_refs or []
        )
        
        self._messages.append(message)
        
        if save_to_file:
            filename = f"{self._message_counter:04d}_{from_agent}_to_{to_agent}.json"
            filepath = self.workspace_dir / "messages" / filename
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(message.to_dict(), f, indent=2, ensure_ascii=False)
        
        # 로깅
        icon = {
            "request": "📤",
            "response": "📥",
            "data": "📦",
            "error": "❌"
        }.get(message_type, "💬")
        
        logger.info(f"{icon} [{from_agent}] → [{to_agent}]: {message_type}")
        
        return message
    
    def get_message_history(
        self,
        agent: str = None,
        message_type: str = None
    ) -> List[AgentMessage]:
        """
        메시지 히스토리 조회
        
        Args:
            agent: 특정 에이전트 필터
            message_type: 특정 타입 필터
            
        Returns:
            메시지 목록
        """
        messages = self._messages
        
        if agent:
            messages = [
                m for m in messages 
                if m.from_agent == agent or m.to_agent == agent
            ]
        
        if message_type:
            messages = [m for m in messages if m.message_type == message_type]
        
        return messages
    
    def print_message_history(self, limit: int = 20):
        """메시지 히스토리 출력"""
        print("\n" + "="*70)
        print("📨 에이전트 간 메시지 히스토리")
        print("="*70)
        
        messages = self._messages[-limit:]
        
        for i, msg in enumerate(messages, 1):
            icon = {
                "request": "📤",
                "response": "📥",
                "data": "📦",
                "error": "❌"
            }.get(msg.message_type, "💬")
            
            time = msg.timestamp.split("T")[1].split(".")[0]
            print(f"\n{i}. [{time}] {icon} {msg.from_agent} → {msg.to_agent}")
            print(f"   Type: {msg.message_type}")
            
            # 내용 요약
            content_str = json.dumps(msg.content, ensure_ascii=False)
            if len(content_str) > 100:
                content_str = content_str[:100] + "..."
            print(f"   Content: {content_str}")
            
            if msg.file_refs:
                print(f"   Files: {', '.join(msg.file_refs)}")
        
        print("\n" + "="*70)
    
    def export_conversation(self, filepath: str = None) -> str:
        """대화 내용 내보내기"""
        if filepath is None:
            filepath = self.workspace_dir / "conversation_log.json"
        
        data = {
            "workspace": str(self.workspace_dir.absolute()),
            "total_messages": len(self._messages),
            "messages": [m.to_dict() for m in self._messages]
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return str(filepath)
    
    # ==========================================
    # 유틸리티
    # ==========================================
    
    def clear(self):
        """워크스페이스 초기화"""
        import shutil
        if self.workspace_dir.exists():
            shutil.rmtree(self.workspace_dir)
        self._init_directories()
        self._messages = []
        self._message_counter = 0
    
    def get_summary(self) -> Dict:
        """워크스페이스 요약"""
        return {
            "path": str(self.workspace_dir.absolute()),
            "data_files": self.list_data_files(),
            "artifacts": self.list_artifacts(),
            "total_messages": len(self._messages),
            "message_types": {
                mtype: len([m for m in self._messages if m.message_type == mtype])
                for mtype in ["request", "response", "data", "error"]
            }
        }


# 전역 워크스페이스 (싱글톤)
_workspace: Optional[AgentWorkspace] = None


def get_workspace(workspace_dir: str = None) -> AgentWorkspace:
    """전역 워크스페이스 가져오기"""
    global _workspace
    
    if _workspace is None or (workspace_dir and str(_workspace.workspace_dir) != workspace_dir):
        _workspace = AgentWorkspace(workspace_dir or "./agent_workspace")
    
    return _workspace
