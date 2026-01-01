"""
로드밸런싱 전략

다양한 로드밸런싱 알고리즘을 구현합니다.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Optional
import random
import threading

from .endpoint import EndpointState


class BalancingStrategy(Enum):
    """로드밸런싱 전략 열거형"""
    ROUND_ROBIN = "round_robin"       # 순차 분배
    WEIGHTED = "weighted"             # 가중치 기반
    LEAST_CONNECTIONS = "least_conn"  # 최소 연결
    RANDOM = "random"                 # 랜덤 선택


class BaseStrategy(ABC):
    """로드밸런싱 전략 기본 클래스"""
    
    @abstractmethod
    def select(self, endpoints: List[EndpointState]) -> Optional[EndpointState]:
        """
        다음 요청을 처리할 엔드포인트 선택
        
        Args:
            endpoints: 사용 가능한 엔드포인트 상태 목록
            
        Returns:
            선택된 엔드포인트 상태, 없으면 None
        """
        pass
    
    def _filter_healthy(self, endpoints: List[EndpointState]) -> List[EndpointState]:
        """정상 상태의 엔드포인트만 필터링"""
        return [ep for ep in endpoints if ep.is_healthy]


class RoundRobinStrategy(BaseStrategy):
    """
    라운드 로빈 전략
    
    순서대로 각 엔드포인트에 요청을 분배합니다.
    """
    
    def __init__(self):
        self._index = 0
        self._lock = threading.Lock()
    
    def select(self, endpoints: List[EndpointState]) -> Optional[EndpointState]:
        healthy = self._filter_healthy(endpoints)
        if not healthy:
            return None
        
        with self._lock:
            self._index = self._index % len(healthy)
            selected = healthy[self._index]
            self._index += 1
            return selected


class WeightedStrategy(BaseStrategy):
    """
    가중치 기반 전략
    
    각 엔드포인트의 가중치에 비례하여 요청을 분배합니다.
    예: weight=2인 엔드포인트는 weight=1보다 2배 많은 요청을 받습니다.
    """
    
    def select(self, endpoints: List[EndpointState]) -> Optional[EndpointState]:
        healthy = self._filter_healthy(endpoints)
        if not healthy:
            return None
        
        # 가중치 목록 생성
        weights = [ep.endpoint.weight for ep in healthy]
        total_weight = sum(weights)
        
        if total_weight == 0:
            return random.choice(healthy)
        
        # 가중치에 따른 랜덤 선택
        r = random.uniform(0, total_weight)
        cumulative = 0
        
        for ep, weight in zip(healthy, weights):
            cumulative += weight
            if r <= cumulative:
                return ep
        
        return healthy[-1]


class LeastConnectionsStrategy(BaseStrategy):
    """
    최소 연결 전략
    
    현재 활성 연결이 가장 적은 엔드포인트를 선택합니다.
    """
    
    def select(self, endpoints: List[EndpointState]) -> Optional[EndpointState]:
        healthy = self._filter_healthy(endpoints)
        if not healthy:
            return None
        
        # 활성 연결이 가장 적은 엔드포인트 선택
        return min(healthy, key=lambda ep: ep.active_connections)


class RandomStrategy(BaseStrategy):
    """
    랜덤 전략
    
    정상 상태의 엔드포인트 중 무작위로 선택합니다.
    """
    
    def select(self, endpoints: List[EndpointState]) -> Optional[EndpointState]:
        healthy = self._filter_healthy(endpoints)
        if not healthy:
            return None
        
        return random.choice(healthy)


# 전략 매핑
_STRATEGY_MAP = {
    BalancingStrategy.ROUND_ROBIN: RoundRobinStrategy,
    BalancingStrategy.WEIGHTED: WeightedStrategy,
    BalancingStrategy.LEAST_CONNECTIONS: LeastConnectionsStrategy,
    BalancingStrategy.RANDOM: RandomStrategy,
}


def get_strategy(strategy: BalancingStrategy) -> BaseStrategy:
    """
    전략 열거형에서 전략 인스턴스 생성
    
    Args:
        strategy: 로드밸런싱 전략 열거형
        
    Returns:
        해당 전략의 인스턴스
    """
    strategy_class = _STRATEGY_MAP.get(strategy)
    if not strategy_class:
        raise ValueError(f"지원하지 않는 전략입니다: {strategy}")
    return strategy_class()


def get_strategy_by_name(name: str) -> BaseStrategy:
    """
    전략 이름에서 전략 인스턴스 생성
    
    Args:
        name: 전략 이름 (round_robin, weighted, least_conn, random)
        
    Returns:
        해당 전략의 인스턴스
    """
    try:
        strategy = BalancingStrategy(name.lower())
        return get_strategy(strategy)
    except ValueError:
        raise ValueError(f"지원하지 않는 전략입니다: {name}")
