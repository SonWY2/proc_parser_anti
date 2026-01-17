"""
메모리 시스템

에이전트의 장기 기억을 관리합니다.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from pathlib import Path
from datetime import datetime
import json


@dataclass
class MemoryEntry:
    """메모리 항목"""
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    relevance_score: float = 0.0
    tags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def matches_tags(self, query_tags: List[str]) -> bool:
        """태그 매칭 확인"""
        if not query_tags:
            return True
        return bool(set(self.tags) & set(query_tags))


class SimpleMemory:
    """단순 키워드 기반 메모리
    
    텍스트 기반 검색을 통해 관련 기억을 찾습니다.
    외부 벡터 DB 없이 로컬에서 동작합니다.
    """
    
    def __init__(self, storage_path: Optional[str] = None, max_entries: int = 1000):
        """
        Args:
            storage_path: 메모리 저장 파일 경로
            max_entries: 최대 항목 수
        """
        self.storage_path = Path(storage_path) if storage_path else None
        self.max_entries = max_entries
        self.entries: List[MemoryEntry] = []
        
        if self.storage_path and self.storage_path.exists():
            self._load()
    
    def add(
        self, 
        content: str, 
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ) -> MemoryEntry:
        """
        메모리 추가
        
        Args:
            content: 저장할 내용
            metadata: 추가 메타데이터
            tags: 분류 태그
            
        Returns:
            생성된 메모리 항목
        """
        entry = MemoryEntry(
            content=content,
            metadata=metadata or {},
            tags=tags or []
        )
        self.entries.append(entry)
        
        # 최대 개수 초과 시 오래된 항목 제거
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]
        
        self._save()
        return entry
    
    def search(
        self, 
        query: str, 
        top_k: int = 5,
        tags: Optional[List[str]] = None
    ) -> List[MemoryEntry]:
        """
        키워드 기반 검색
        
        Args:
            query: 검색 쿼리
            top_k: 반환할 최대 결과 수
            tags: 필터링할 태그
            
        Returns:
            관련도 순으로 정렬된 메모리 항목 목록
        """
        query_words = set(query.lower().split())
        
        scored_entries: List[MemoryEntry] = []
        for entry in self.entries:
            # 태그 필터링
            if tags and not entry.matches_tags(tags):
                continue
            
            # 키워드 매칭
            content_words = set(entry.content.lower().split())
            overlap = len(query_words & content_words)
            
            if overlap > 0:
                # 관련도 점수 계산 (중복 단어 수 / 쿼리 단어 수)
                entry.relevance_score = overlap / len(query_words)
                scored_entries.append(entry)
        
        # 관련도 순 정렬
        scored_entries.sort(key=lambda x: x.relevance_score, reverse=True)
        return scored_entries[:top_k]
    
    def search_by_metadata(
        self, 
        key: str, 
        value: Any
    ) -> List[MemoryEntry]:
        """메타데이터 기반 검색"""
        return [
            entry for entry in self.entries
            if entry.metadata.get(key) == value
        ]
    
    def search_by_tags(self, tags: List[str]) -> List[MemoryEntry]:
        """태그 기반 검색"""
        return [
            entry for entry in self.entries
            if entry.matches_tags(tags)
        ]
    
    def get_recent(self, count: int = 10) -> List[MemoryEntry]:
        """최근 메모리 조회"""
        return list(reversed(self.entries[-count:]))
    
    def clear(self) -> None:
        """모든 메모리 삭제"""
        self.entries.clear()
        self._save()
    
    def remove_by_tags(self, tags: List[str]) -> int:
        """특정 태그의 메모리 삭제"""
        before_count = len(self.entries)
        self.entries = [
            entry for entry in self.entries
            if not entry.matches_tags(tags)
        ]
        removed = before_count - len(self.entries)
        if removed > 0:
            self._save()
        return removed
    
    def stats(self) -> Dict[str, Any]:
        """메모리 통계"""
        all_tags: Dict[str, int] = {}
        for entry in self.entries:
            for tag in entry.tags:
                all_tags[tag] = all_tags.get(tag, 0) + 1
        
        return {
            "total_entries": len(self.entries),
            "max_entries": self.max_entries,
            "storage_path": str(self.storage_path) if self.storage_path else None,
            "tags": all_tags
        }
    
    def _save(self) -> None:
        """메모리를 파일에 저장"""
        if not self.storage_path:
            return
        
        data = [
            {
                "content": e.content,
                "metadata": e.metadata,
                "timestamp": e.timestamp,
                "tags": e.tags
            }
            for e in self.entries
        ]
        
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
    
    def _load(self) -> None:
        """파일에서 메모리 로드"""
        if not self.storage_path or not self.storage_path.exists():
            return
        
        try:
            data = json.loads(self.storage_path.read_text(encoding='utf-8'))
            self.entries = [
                MemoryEntry(
                    content=d["content"],
                    metadata=d.get("metadata", {}),
                    timestamp=d.get("timestamp", ""),
                    tags=d.get("tags", [])
                )
                for d in data
            ]
        except Exception as e:
            print(f"메모리 로드 실패: {e}")
            self.entries = []


class ConversationMemory:
    """대화 기록 메모리
    
    에이전트별 대화 기록을 관리합니다.
    """
    
    def __init__(self, storage_dir: Optional[str] = None):
        """
        Args:
            storage_dir: 대화 저장 디렉토리
        """
        self.storage_dir = Path(storage_dir) if storage_dir else None
        self.conversations: Dict[str, List[Dict[str, str]]] = {}
    
    def add_message(
        self, 
        conversation_id: str, 
        role: str, 
        content: str
    ) -> None:
        """메시지 추가"""
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []
        
        self.conversations[conversation_id].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        
        self._save_conversation(conversation_id)
    
    def get_messages(
        self, 
        conversation_id: str, 
        limit: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """대화 메시지 조회"""
        messages = self.conversations.get(conversation_id, [])
        if limit:
            return messages[-limit:]
        return messages
    
    def clear_conversation(self, conversation_id: str) -> None:
        """대화 초기화"""
        self.conversations[conversation_id] = []
        self._save_conversation(conversation_id)
    
    def list_conversations(self) -> List[str]:
        """대화 ID 목록"""
        return list(self.conversations.keys())
    
    def _save_conversation(self, conversation_id: str) -> None:
        """대화 저장"""
        if not self.storage_dir:
            return
        
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.storage_dir / f"{conversation_id}.json"
        
        data = self.conversations.get(conversation_id, [])
        file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
    
    def load_conversation(self, conversation_id: str) -> bool:
        """대화 로드"""
        if not self.storage_dir:
            return False
        
        file_path = self.storage_dir / f"{conversation_id}.json"
        if not file_path.exists():
            return False
        
        try:
            data = json.loads(file_path.read_text(encoding='utf-8'))
            self.conversations[conversation_id] = data
            return True
        except Exception:
            return False
