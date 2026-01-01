"""
엔드포인트 데이터 클래스

API 엔드포인트 정보와 상태를 관리하는 데이터 클래스입니다.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class Endpoint:
    """단일 API 엔드포인트 정보"""
    url: str                              # API base URL (예: http://localhost:8000/v1)
    api_key: Optional[str] = None         # API 키 (선택)
    weight: int = 1                       # 가중치 (Weighted 전략용)
    name: Optional[str] = None            # 별칭 (선택)
    max_connections: int = 100            # 최대 동시 연결
    max_tokens: int = 4096                # 해당 엔드포인트의 기본 max_tokens
    temperature: float = 0.7              # 해당 엔드포인트의 기본 temperature
    
    def __post_init__(self):
        """URL 정규화"""
        self.url = self.url.rstrip('/')
        if not self.name:
            self.name = self.url


@dataclass
class EndpointState:
    """엔드포인트 상태 추적"""
    endpoint: Endpoint
    is_healthy: bool = True
    active_connections: int = 0
    total_requests: int = 0
    total_failures: int = 0
    total_success: int = 0
    last_check: Optional[datetime] = None
    last_error: Optional[str] = None
    last_response_time: Optional[float] = None  # 마지막 응답 시간 (초)
    
    @property
    def failure_rate(self) -> float:
        """실패율 계산"""
        if self.total_requests == 0:
            return 0.0
        return self.total_failures / self.total_requests
    
    @property
    def success_rate(self) -> float:
        """성공률 계산"""
        return 1.0 - self.failure_rate
    
    def record_request(self):
        """요청 시작 기록"""
        self.total_requests += 1
        self.active_connections += 1
    
    def record_success(self, response_time: float):
        """성공 응답 기록"""
        self.active_connections = max(0, self.active_connections - 1)
        self.total_success += 1
        self.last_response_time = response_time
        self.last_error = None
    
    def record_failure(self, error: str):
        """실패 응답 기록"""
        self.active_connections = max(0, self.active_connections - 1)
        self.total_failures += 1
        self.last_error = error
    
    def mark_healthy(self):
        """엔드포인트를 정상 상태로 표시"""
        self.is_healthy = True
        self.last_check = datetime.now()
    
    def mark_unhealthy(self, error: str):
        """엔드포인트를 비정상 상태로 표시"""
        self.is_healthy = False
        self.last_check = datetime.now()
        self.last_error = error
    
    def to_dict(self) -> dict:
        """상태를 딕셔너리로 변환"""
        return {
            'name': self.endpoint.name,
            'url': self.endpoint.url,
            'is_healthy': self.is_healthy,
            'active_connections': self.active_connections,
            'total_requests': self.total_requests,
            'total_success': self.total_success,
            'total_failures': self.total_failures,
            'success_rate': f"{self.success_rate:.2%}",
            'last_response_time': self.last_response_time,
            'last_error': self.last_error,
            'last_check': self.last_check.isoformat() if self.last_check else None,
        }
