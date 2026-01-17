"""
메인 로드밸런서 클래스

OpenAI 호환 API 로드밸런서의 핵심 구현입니다.
"""

import os
import json
import time
import threading
from typing import List, Dict, Any, Optional
import requests
import yaml

from .endpoint import Endpoint, EndpointState
from .strategies import BalancingStrategy, get_strategy, get_strategy_by_name, BaseStrategy
from .health_check import HealthChecker


class LoadBalancer:
    """
    OpenAI 호환 API 로드밸런서
    
    여러 API 엔드포인트에 요청을 분산시키고, 장애 발생 시 자동으로
    다른 엔드포인트로 요청을 재시도합니다.
    """
    
    def __init__(
        self,
        endpoints: List[Endpoint],
        strategy: BalancingStrategy = BalancingStrategy.ROUND_ROBIN,
        enable_health_check: bool = True,
        health_check_interval: int = 30,
        retry_count: int = 2,
        fallback_on_failure: bool = True,
        timeout: int = 60
    ):
        """
        Args:
            endpoints: API 엔드포인트 목록
            strategy: 로드밸런싱 전략
            enable_health_check: 헬스 체크 활성화 여부
            health_check_interval: 헬스 체크 주기 (초)
            retry_count: 실패 시 재시도 횟수
            fallback_on_failure: 실패 시 다른 엔드포인트로 폴백 여부
            timeout: 요청 타임아웃 (초)
        """
        if not endpoints:
            raise ValueError("최소 하나 이상의 엔드포인트가 필요합니다")
        
        self._endpoints: List[EndpointState] = [
            EndpointState(endpoint=ep) for ep in endpoints
        ]
        self._strategy: BaseStrategy = get_strategy(strategy)
        self._strategy_type = strategy
        self._retry_count = retry_count
        self._fallback_on_failure = fallback_on_failure
        self._timeout = timeout
        self._lock = threading.Lock()
        
        # 모델 이름 캐시
        self._model_cache: Dict[str, Optional[str]] = {}
        
        # 헬스 체커
        self._health_checker: Optional[HealthChecker] = None
        if enable_health_check:
            self._health_checker = HealthChecker(
                check_interval=health_check_interval,
                timeout=min(timeout, 10)
            )
            self._health_checker.start(
                self._endpoints,
                callback=self._on_health_change
            )
    
    def _on_health_change(self, endpoint_state: EndpointState, is_healthy: bool):
        """헬스 상태 변경 콜백"""
        status = "정상" if is_healthy else "비정상"
        # 로깅 대신 내부 상태만 업데이트 (필요시 로깅 추가)
        pass
    
    @classmethod
    def from_env(cls) -> 'LoadBalancer':
        """
        환경변수에서 설정 로드
        
        환경변수:
            LLM_ENDPOINTS: 콤마로 구분된 엔드포인트 URL 목록
            LLM_API_KEYS: 콤마로 구분된 API 키 목록 (선택, 엔드포인트 순서와 매칭)
            LLM_WEIGHTS: 콤마로 구분된 가중치 목록 (선택)
            LLM_STRATEGY: 로드밸런싱 전략 (round_robin, weighted, least_conn, random)
            LLM_HEALTH_CHECK: 헬스 체크 활성화 (true/false)
            LLM_TIMEOUT: 요청 타임아웃 (초)
        """
        endpoints_str = os.getenv('LLM_ENDPOINTS', '')
        if not endpoints_str:
            raise ValueError("LLM_ENDPOINTS 환경변수가 설정되지 않았습니다")
        
        urls = [url.strip() for url in endpoints_str.split(',') if url.strip()]
        
        # API 키 파싱
        keys_str = os.getenv('LLM_API_KEYS', '')
        api_keys = [key.strip() for key in keys_str.split(',')] if keys_str else []
        
        # 가중치 파싱
        weights_str = os.getenv('LLM_WEIGHTS', '')
        weights = []
        if weights_str:
            weights = [int(w.strip()) for w in weights_str.split(',') if w.strip()]
        
        # max_tokens 파싱
        max_tokens_str = os.getenv('LLM_MAX_TOKENS', '')
        max_tokens_list = []
        if max_tokens_str:
            max_tokens_list = [int(t.strip()) for t in max_tokens_str.split(',') if t.strip()]
        
        # temperature 파싱
        temp_str = os.getenv('LLM_TEMPERATURES', '')
        temp_list = []
        if temp_str:
            temp_list = [float(t.strip()) for t in temp_str.split(',') if t.strip()]
        
        # 엔드포인트 생성
        endpoints = []
        for i, url in enumerate(urls):
            endpoints.append(Endpoint(
                url=url,
                api_key=api_keys[i] if i < len(api_keys) else None,
                weight=weights[i] if i < len(weights) else 1,
                max_tokens=max_tokens_list[i] if i < len(max_tokens_list) else 4096,
                temperature=temp_list[i] if i < len(temp_list) else 0.7,
            ))
        
        # 전략 파싱
        strategy_name = os.getenv('LLM_STRATEGY', 'round_robin')
        strategy = BalancingStrategy(strategy_name.lower())
        
        # 기타 설정
        enable_health = os.getenv('LLM_HEALTH_CHECK', 'true').lower() == 'true'
        timeout = int(os.getenv('LLM_TIMEOUT', '60'))
        
        return cls(
            endpoints=endpoints,
            strategy=strategy,
            enable_health_check=enable_health,
            timeout=timeout
        )
    
    @classmethod
    def from_config(cls, config_path: str) -> 'LoadBalancer':
        """
        YAML/JSON 설정 파일에서 로드
        
        Args:
            config_path: 설정 파일 경로
        """
        with open(config_path, 'r', encoding='utf-8') as f:
            if config_path.endswith('.json'):
                config = json.load(f)
            else:
                config = yaml.safe_load(f)
        
        # 엔드포인트 파싱
        endpoints = []
        for ep_config in config.get('endpoints', []):
            endpoints.append(Endpoint(
                url=ep_config['url'],
                api_key=ep_config.get('api_key'),
                weight=ep_config.get('weight', 1),
                name=ep_config.get('name'),
                max_connections=ep_config.get('max_connections', 100),
                max_tokens=ep_config.get('max_tokens', 4096),
                temperature=ep_config.get('temperature', 0.7),
            ))
        
        if not endpoints:
            raise ValueError("설정에 엔드포인트가 없습니다")
        
        # 전략 파싱
        strategy_name = config.get('strategy', 'round_robin')
        strategy = BalancingStrategy(strategy_name.lower())
        
        # 헬스 체크 설정
        health_config = config.get('health_check', {})
        enable_health = health_config.get('enabled', True)
        health_interval = health_config.get('interval', 30)
        
        # 기타 설정
        retry_count = config.get('retry_count', 2)
        fallback = config.get('fallback_on_failure', True)
        timeout = config.get('timeout', 60)
        
        return cls(
            endpoints=endpoints,
            strategy=strategy,
            enable_health_check=enable_health,
            health_check_interval=health_interval,
            retry_count=retry_count,
            fallback_on_failure=fallback,
            timeout=timeout
        )
    
    def add_endpoint(self, endpoint: Endpoint) -> None:
        """런타임에 엔드포인트 추가"""
        with self._lock:
            self._endpoints.append(EndpointState(endpoint=endpoint))
    
    def remove_endpoint(self, url: str) -> bool:
        """
        엔드포인트 제거
        
        Args:
            url: 제거할 엔드포인트 URL
            
        Returns:
            제거 성공 여부
        """
        with self._lock:
            for i, ep_state in enumerate(self._endpoints):
                if ep_state.endpoint.url == url.rstrip('/'):
                    self._endpoints.pop(i)
                    return True
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        통계 조회
        
        Returns:
            로드밸런서 통계 정보
        """
        with self._lock:
            endpoints_stats = [ep.to_dict() for ep in self._endpoints]
            total_requests = sum(ep.total_requests for ep in self._endpoints)
            total_success = sum(ep.total_success for ep in self._endpoints)
            total_failures = sum(ep.total_failures for ep in self._endpoints)
            healthy_count = sum(1 for ep in self._endpoints if ep.is_healthy)
        
        return {
            'strategy': self._strategy_type.value,
            'endpoints': endpoints_stats,
            'total_endpoints': len(endpoints_stats),
            'healthy_endpoints': healthy_count,
            'total_requests': total_requests,
            'total_success': total_success,
            'total_failures': total_failures,
            'success_rate': f"{total_success / total_requests:.2%}" if total_requests > 0 else "N/A",
        }
    
    def _get_model_name(self, endpoint: Endpoint) -> Optional[str]:
        """엔드포인트의 모델 이름 조회"""
        cache_key = endpoint.url
        
        if cache_key in self._model_cache:
            return self._model_cache[cache_key]
        
        try:
            headers = {}
            if endpoint.api_key:
                headers['Authorization'] = f'Bearer {endpoint.api_key}'
            
            response = requests.get(
                f"{endpoint.url}/models",
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            models = data.get('data', [])
            
            if models:
                model_name = models[0].get('id')
                self._model_cache[cache_key] = model_name
                return model_name
        except Exception:
            pass
        
        return None
    
    def _call_endpoint(
        self,
        endpoint_state: EndpointState,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """단일 엔드포인트에 요청"""
        endpoint = endpoint_state.endpoint
        
        # 엔드포인트 기본값 사용 (호출 시 파라미터가 없으면)
        actual_temperature = temperature if temperature is not None else endpoint.temperature
        actual_max_tokens = max_tokens if max_tokens is not None else endpoint.max_tokens
        
        # 모델 이름 조회
        model_name = self._get_model_name(endpoint)
        if not model_name:
            return {
                'success': False,
                'content': '',
                'tool_calls': [],
                'error': '모델을 찾을 수 없습니다',
                'usage': {},
                'endpoint': endpoint.name
            }
        
        start_time = time.time()
        endpoint_state.record_request()
        
        try:
            headers = {'Content-Type': 'application/json'}
            if endpoint.api_key:
                headers['Authorization'] = f'Bearer {endpoint.api_key}'
            
            payload = {
                'model': model_name,
                'messages': messages,
                'temperature': actual_temperature,
                'max_tokens': actual_max_tokens
            }
            
            # 도구가 있으면 추가
            if tools:
                payload['tools'] = [
                    {'type': 'function', 'function': tool}
                    for tool in tools
                ]
                payload['tool_choice'] = 'auto'
            
            response = requests.post(
                f"{endpoint.url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self._timeout
            )
            response.raise_for_status()
            
            result = response.json()
            choice = result['choices'][0]
            message = choice['message']
            
            # 도구 호출 파싱
            tool_calls = []
            if 'tool_calls' in message:
                for tc in message['tool_calls']:
                    tool_calls.append({
                        'id': tc.get('id', ''),
                        'name': tc['function']['name'],
                        'arguments': json.loads(tc['function']['arguments'])
                    })
            
            elapsed = time.time() - start_time
            endpoint_state.record_success(elapsed)
            
            return {
                'success': True,
                'content': message.get('content', ''),
                'tool_calls': tool_calls,
                'error': '',
                'usage': result.get('usage', {}),
                'endpoint': endpoint.name,
                'response_time': elapsed
            }
            
        except requests.Timeout:
            error = f'요청 시간 초과 ({self._timeout}초)'
            endpoint_state.record_failure(error)
            return {
                'success': False,
                'content': '',
                'tool_calls': [],
                'error': error,
                'usage': {},
                'endpoint': endpoint.name
            }
        except requests.RequestException as e:
            error = f'API 요청 실패: {str(e)}'
            endpoint_state.record_failure(error)
            return {
                'success': False,
                'content': '',
                'tool_calls': [],
                'error': error,
                'usage': {},
                'endpoint': endpoint.name
            }
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            error = f'응답 파싱 실패: {str(e)}'
            endpoint_state.record_failure(error)
            return {
                'success': False,
                'content': '',
                'tool_calls': [],
                'error': error,
                'usage': {},
                'endpoint': endpoint.name
            }
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Chat completion API 호출 (로드밸런싱 적용)
        
        기존 LLMClient.chat()과 동일한 인터페이스입니다.
        실패 시 다른 엔드포인트로 자동 재시도합니다.
        
        Args:
            messages: 대화 메시지 목록 [{"role": "user", "content": "..."}]
            tools: 사용 가능한 도구 스키마 목록
            temperature: 생성 온도 (None이면 엔드포인트 기본값 사용)
            max_tokens: 최대 토큰 수 (None이면 엔드포인트 기본값 사용)
            
        Returns:
            {
                'success': bool,
                'content': str,
                'tool_calls': List[Dict],
                'error': str,
                'usage': Dict,
                'endpoint': str  # 사용된 엔드포인트 이름
            }
        """
        tried_endpoints = set()
        last_error = ""
        
        for attempt in range(self._retry_count + 1):
            # 엔드포인트 선택
            with self._lock:
                available = [
                    ep for ep in self._endpoints 
                    if id(ep) not in tried_endpoints
                ]
            
            if not available:
                break
            
            endpoint_state = self._strategy.select(available)
            if not endpoint_state:
                break
            
            tried_endpoints.add(id(endpoint_state))
            
            # 요청 시도
            result = self._call_endpoint(
                endpoint_state, messages, tools, temperature, max_tokens
            )
            
            if result['success']:
                return result
            
            last_error = result['error']
            
            # 폴백이 비활성화되면 첫 번째 실패에서 종료
            if not self._fallback_on_failure:
                return result
        
        # 모든 시도 실패
        return {
            'success': False,
            'content': '',
            'tool_calls': [],
            'error': f'모든 엔드포인트 실패. 마지막 오류: {last_error}',
            'usage': {},
            'endpoint': None
        }
    
    def close(self):
        """리소스 정리"""
        if self._health_checker:
            self._health_checker.stop()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
