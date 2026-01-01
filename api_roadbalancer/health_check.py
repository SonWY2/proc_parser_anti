"""
헬스 체크

엔드포인트의 상태를 주기적으로 확인합니다.
"""

import threading
import time
from typing import List, Callable, Optional
import requests

from .endpoint import Endpoint, EndpointState


class HealthChecker:
    """
    엔드포인트 헬스 체크
    
    백그라운드에서 주기적으로 각 엔드포인트의 상태를 확인하고
    비정상 엔드포인트를 자동으로 제외합니다.
    """
    
    def __init__(
        self,
        check_interval: int = 30,
        timeout: int = 5,
        failure_threshold: int = 3,
        recovery_threshold: int = 1
    ):
        """
        Args:
            check_interval: 헬스 체크 주기 (초)
            timeout: 요청 타임아웃 (초)
            failure_threshold: 연속 실패 횟수가 이 값 이상이면 비정상 처리
            recovery_threshold: 연속 성공 횟수가 이 값 이상이면 정상 복구
        """
        self.check_interval = check_interval
        self.timeout = timeout
        self.failure_threshold = failure_threshold
        self.recovery_threshold = recovery_threshold
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._endpoints: List[EndpointState] = []
        self._callback: Optional[Callable[[EndpointState, bool], None]] = None
        
        # 연속 실패/성공 카운터
        self._consecutive_failures: dict = {}
        self._consecutive_successes: dict = {}
    
    def check_endpoint(self, endpoint: Endpoint) -> tuple[bool, Optional[str]]:
        """
        단일 엔드포인트 상태 확인
        
        /models 엔드포인트를 호출하여 서버 상태를 확인합니다.
        
        Args:
            endpoint: 확인할 엔드포인트
            
        Returns:
            (is_healthy, error_message) 튜플
        """
        try:
            headers = {}
            if endpoint.api_key:
                headers['Authorization'] = f'Bearer {endpoint.api_key}'
            
            response = requests.get(
                f"{endpoint.url}/models",
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            # 응답이 올바른 형식인지 확인
            data = response.json()
            if 'data' in data or 'object' in data:
                return True, None
            else:
                return False, "잘못된 응답 형식"
                
        except requests.Timeout:
            return False, f"타임아웃 ({self.timeout}초)"
        except requests.ConnectionError:
            return False, "연결 실패"
        except requests.RequestException as e:
            return False, str(e)
        except Exception as e:
            return False, f"알 수 없는 오류: {e}"
    
    def _check_all(self):
        """모든 엔드포인트 상태 확인"""
        for ep_state in self._endpoints:
            ep_id = id(ep_state)
            is_healthy, error = self.check_endpoint(ep_state.endpoint)
            
            if is_healthy:
                # 연속 성공 카운트
                self._consecutive_failures[ep_id] = 0
                self._consecutive_successes[ep_id] = self._consecutive_successes.get(ep_id, 0) + 1
                
                # 복구 임계값 도달 시 정상 상태로 변경
                if (not ep_state.is_healthy and 
                    self._consecutive_successes[ep_id] >= self.recovery_threshold):
                    ep_state.mark_healthy()
                    if self._callback:
                        self._callback(ep_state, True)
                elif ep_state.is_healthy:
                    ep_state.mark_healthy()
            else:
                # 연속 실패 카운트
                self._consecutive_successes[ep_id] = 0
                self._consecutive_failures[ep_id] = self._consecutive_failures.get(ep_id, 0) + 1
                
                # 실패 임계값 도달 시 비정상 상태로 변경
                if (ep_state.is_healthy and 
                    self._consecutive_failures[ep_id] >= self.failure_threshold):
                    ep_state.mark_unhealthy(error or "헬스 체크 실패")
                    if self._callback:
                        self._callback(ep_state, False)
    
    def _run(self):
        """백그라운드 스레드 실행"""
        while self._running:
            try:
                self._check_all()
            except Exception:
                pass  # 헬스 체크 오류는 무시
            
            # 인터벌 동안 대기 (중간에 stop 가능하도록 작은 단위로 분할)
            for _ in range(self.check_interval * 10):
                if not self._running:
                    break
                time.sleep(0.1)
    
    def start(
        self,
        endpoints: List[EndpointState],
        callback: Optional[Callable[[EndpointState, bool], None]] = None
    ):
        """
        백그라운드 헬스 체크 시작
        
        Args:
            endpoints: 모니터링할 엔드포인트 상태 목록
            callback: 상태 변경 시 호출될 콜백 (endpoint_state, is_healthy)
        """
        if self._running:
            return
        
        self._endpoints = endpoints
        self._callback = callback
        self._running = True
        self._consecutive_failures.clear()
        self._consecutive_successes.clear()
        
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
    
    def stop(self):
        """헬스 체크 중지"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
    
    def check_now(self):
        """즉시 헬스 체크 수행"""
        self._check_all()
