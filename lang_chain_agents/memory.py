"""
에피소딕 메모리 시스템

Self-Evolve를 위한 과거 경험 및 학습된 교훈 저장/검색
"""
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
from pathlib import Path


@dataclass
class Episode:
    """하나의 작업 에피소드"""
    
    task: str                       # 수행한 작업
    agent: str                      # 사용된 에이전트
    actions: list[str]              # 수행한 액션들
    outcome: str                    # 결과 (success/failure)
    quality_score: float            # 품질 점수 (1-10)
    reflection: str                 # 반성 내용
    lesson: str                     # 학습된 교훈
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "Episode":
        return cls(**data)


class EpisodicMemory:
    """
    에피소딕 메모리: 과거 경험 및 학습 저장
    
    Self-Evolve 기능을 위해 과거 작업의 결과와 교훈을 저장하고
    유사한 작업 수행 시 참조할 수 있도록 합니다.
    """
    
    def __init__(
        self, 
        max_episodes: int = 100,
        persist_path: Optional[str] = None
    ):
        self.max_episodes = max_episodes
        self.persist_path = Path(persist_path) if persist_path else None
        
        self.episodes: list[Episode] = []
        self.lessons_learned: dict[str, str] = {}  # key: 상황, value: 교훈
        
        if self.persist_path and self.persist_path.exists():
            self._load()
    
    def add_episode(
        self,
        task: str,
        agent: str,
        actions: list[str],
        outcome: str,
        quality_score: float,
        reflection: str,
        lesson: str = ""
    ) -> Episode:
        """
        새 에피소드 추가
        
        Args:
            task: 수행한 작업
            agent: 사용된 에이전트
            actions: 수행한 액션들
            outcome: 결과 (success/failure)
            quality_score: 품질 점수 (1-10)
            reflection: 반성 내용
            lesson: 학습된 교훈
        
        Returns:
            생성된 Episode
        """
        episode = Episode(
            task=task,
            agent=agent,
            actions=actions,
            outcome=outcome,
            quality_score=quality_score,
            reflection=reflection,
            lesson=lesson,
        )
        
        self.episodes.append(episode)
        
        # 최대 에피소드 수 제한
        if len(self.episodes) > self.max_episodes:
            self.episodes = self.episodes[-self.max_episodes:]
        
        # 교훈 저장
        if lesson:
            self.update_lesson(task, lesson)
        
        # 영속화
        if self.persist_path:
            self._save()
        
        return episode
    
    def get_relevant_lessons(
        self, 
        current_task: str, 
        k: int = 5
    ) -> list[str]:
        """
        현재 작업과 관련된 교훈 검색
        
        Args:
            current_task: 현재 작업 설명
            k: 반환할 최대 교훈 수
        
        Returns:
            관련 교훈 목록
        """
        # 간단한 키워드 매칭 (향후 임베딩 기반 검색으로 개선 가능)
        task_lower = current_task.lower()
        relevant = []
        
        for key, lesson in self.lessons_learned.items():
            key_lower = key.lower()
            # 키워드 겹침 확인
            task_words = set(task_lower.split())
            key_words = set(key_lower.split())
            overlap = task_words & key_words
            
            if overlap:
                relevant.append((len(overlap), lesson))
        
        # 겹침이 많은 순으로 정렬
        relevant.sort(key=lambda x: x[0], reverse=True)
        
        return [lesson for _, lesson in relevant[:k]]
    
    def get_similar_episodes(
        self,
        task: str,
        agent: Optional[str] = None,
        k: int = 5
    ) -> list[Episode]:
        """
        유사한 과거 에피소드 검색
        
        Args:
            task: 작업 설명
            agent: 에이전트 이름 (선택적 필터)
            k: 반환할 최대 에피소드 수
        
        Returns:
            유사 에피소드 목록
        """
        candidates = self.episodes
        
        if agent:
            candidates = [e for e in candidates if e.agent == agent]
        
        # 간단한 키워드 매칭
        task_words = set(task.lower().split())
        scored = []
        
        for episode in candidates:
            episode_words = set(episode.task.lower().split())
            overlap = len(task_words & episode_words)
            scored.append((overlap, episode))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        
        return [episode for _, episode in scored[:k]]
    
    def update_lesson(self, key: str, insight: str):
        """
        학습된 교훈 업데이트 (Self-Evolve)
        
        Args:
            key: 교훈 키 (상황 설명)
            insight: 교훈 내용
        """
        # 기존 교훈이 있으면 병합
        if key in self.lessons_learned:
            existing = self.lessons_learned[key]
            self.lessons_learned[key] = f"{existing}\n추가: {insight}"
        else:
            self.lessons_learned[key] = insight
        
        if self.persist_path:
            self._save()
    
    def get_statistics(self) -> dict:
        """메모리 통계 반환"""
        if not self.episodes:
            return {
                "total_episodes": 0,
                "success_rate": 0.0,
                "avg_quality": 0.0,
                "lessons_count": len(self.lessons_learned),
            }
        
        successes = sum(1 for e in self.episodes if e.outcome == "success")
        avg_quality = sum(e.quality_score for e in self.episodes) / len(self.episodes)
        
        return {
            "total_episodes": len(self.episodes),
            "success_rate": successes / len(self.episodes),
            "avg_quality": avg_quality,
            "lessons_count": len(self.lessons_learned),
        }
    
    def _save(self):
        """메모리 영속화"""
        if not self.persist_path:
            return
        
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "episodes": [e.to_dict() for e in self.episodes],
            "lessons_learned": self.lessons_learned,
        }
        
        with open(self.persist_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _load(self):
        """저장된 메모리 로드"""
        if not self.persist_path or not self.persist_path.exists():
            return
        
        with open(self.persist_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        self.episodes = [Episode.from_dict(e) for e in data.get("episodes", [])]
        self.lessons_learned = data.get("lessons_learned", {})
    
    def clear(self):
        """메모리 초기화"""
        self.episodes = []
        self.lessons_learned = {}
        
        if self.persist_path and self.persist_path.exists():
            self.persist_path.unlink()
