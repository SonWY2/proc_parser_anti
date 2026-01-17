"""
API Load Balancer 테스트

로드밸런서 모듈의 단위 테스트입니다.
"""

import pytest
from unittest.mock import patch, MagicMock
import json

from api_roadbalancer import (
    Endpoint,
    EndpointState,
    BalancingStrategy,
    get_strategy,
    LoadBalancer,
)
from api_roadbalancer.strategies import (
    RoundRobinStrategy,
    WeightedStrategy,
    LeastConnectionsStrategy,
    RandomStrategy,
)


class TestEndpoint:
    """Endpoint 데이터클래스 테스트"""
    
    def test_endpoint_creation(self):
        """기본 엔드포인트 생성"""
        ep = Endpoint(url="http://localhost:8000/v1")
        assert ep.url == "http://localhost:8000/v1"
        assert ep.weight == 1
        assert ep.max_tokens == 4096
        assert ep.temperature == 0.7
    
    def test_endpoint_with_custom_values(self):
        """커스텀 값으로 엔드포인트 생성"""
        ep = Endpoint(
            url="http://localhost:8000/v1/",
            api_key="test-key",
            weight=2,
            name="GPU-1",
            max_tokens=8192,
            temperature=0.5
        )
        # URL 끝 슬래시 제거 확인
        assert ep.url == "http://localhost:8000/v1"
        assert ep.api_key == "test-key"
        assert ep.weight == 2
        assert ep.name == "GPU-1"
        assert ep.max_tokens == 8192
        assert ep.temperature == 0.5


class TestEndpointState:
    """EndpointState 테스트"""
    
    def test_state_initialization(self):
        """상태 초기화"""
        ep = Endpoint(url="http://localhost:8000/v1")
        state = EndpointState(endpoint=ep)
        
        assert state.is_healthy == True
        assert state.active_connections == 0
        assert state.total_requests == 0
        assert state.failure_rate == 0.0
    
    def test_record_request(self):
        """요청 기록"""
        ep = Endpoint(url="http://localhost:8000/v1")
        state = EndpointState(endpoint=ep)
        
        state.record_request()
        assert state.total_requests == 1
        assert state.active_connections == 1
    
    def test_record_success(self):
        """성공 기록"""
        ep = Endpoint(url="http://localhost:8000/v1")
        state = EndpointState(endpoint=ep)
        
        state.record_request()
        state.record_success(0.5)
        
        assert state.total_success == 1
        assert state.active_connections == 0
        assert state.last_response_time == 0.5
    
    def test_record_failure(self):
        """실패 기록"""
        ep = Endpoint(url="http://localhost:8000/v1")
        state = EndpointState(endpoint=ep)
        
        state.record_request()
        state.record_failure("Connection error")
        
        assert state.total_failures == 1
        assert state.active_connections == 0
        assert state.last_error == "Connection error"
        assert state.failure_rate == 1.0


class TestStrategies:
    """로드밸런싱 전략 테스트"""
    
    def create_endpoints(self, count: int = 3) -> list:
        """테스트용 엔드포인트 상태 목록 생성"""
        return [
            EndpointState(endpoint=Endpoint(
                url=f"http://host{i}:8000/v1",
                weight=i + 1
            ))
            for i in range(count)
        ]
    
    def test_round_robin_strategy(self):
        """라운드 로빈 전략"""
        strategy = RoundRobinStrategy()
        endpoints = self.create_endpoints(3)
        
        # 순차적으로 선택되는지 확인
        selected_urls = []
        for _ in range(6):
            ep = strategy.select(endpoints)
            selected_urls.append(ep.endpoint.url)
        
        # 2번 순환해야 함
        assert selected_urls == [
            "http://host0:8000/v1",
            "http://host1:8000/v1",
            "http://host2:8000/v1",
            "http://host0:8000/v1",
            "http://host1:8000/v1",
            "http://host2:8000/v1",
        ]
    
    def test_round_robin_skips_unhealthy(self):
        """라운드 로빈 - 비정상 엔드포인트 건너뛰기"""
        strategy = RoundRobinStrategy()
        endpoints = self.create_endpoints(3)
        endpoints[1].is_healthy = False
        
        selected = []
        for _ in range(4):
            ep = strategy.select(endpoints)
            selected.append(ep.endpoint.url)
        
        assert "http://host1:8000/v1" not in selected
    
    def test_weighted_strategy(self):
        """가중치 전략 - 분포 테스트"""
        strategy = WeightedStrategy()
        endpoints = self.create_endpoints(3)
        # weights: 1, 2, 3
        
        counts = {0: 0, 1: 0, 2: 0}
        iterations = 1000
        
        for _ in range(iterations):
            ep = strategy.select(endpoints)
            idx = int(ep.endpoint.url.split("host")[1].split(":")[0])
            counts[idx] += 1
        
        # 대략적인 비율 확인 (1:2:3 비율)
        # 허용 오차 10%
        total = sum(counts.values())
        assert abs(counts[0] / total - 1/6) < 0.1
        assert abs(counts[1] / total - 2/6) < 0.1
        assert abs(counts[2] / total - 3/6) < 0.1
    
    def test_least_connections_strategy(self):
        """최소 연결 전략"""
        strategy = LeastConnectionsStrategy()
        endpoints = self.create_endpoints(3)
        
        # 연결 수 설정
        endpoints[0].active_connections = 5
        endpoints[1].active_connections = 2
        endpoints[2].active_connections = 8
        
        selected = strategy.select(endpoints)
        assert selected.endpoint.url == "http://host1:8000/v1"
    
    def test_random_strategy(self):
        """랜덤 전략"""
        strategy = RandomStrategy()
        endpoints = self.create_endpoints(3)
        
        # 모든 엔드포인트가 선택될 수 있는지 확인
        selected_urls = set()
        for _ in range(100):
            ep = strategy.select(endpoints)
            selected_urls.add(ep.endpoint.url)
        
        assert len(selected_urls) == 3
    
    def test_empty_endpoints_returns_none(self):
        """빈 엔드포인트 목록"""
        for strategy in [
            RoundRobinStrategy(),
            WeightedStrategy(),
            LeastConnectionsStrategy(),
            RandomStrategy(),
        ]:
            assert strategy.select([]) is None
    
    def test_all_unhealthy_returns_none(self):
        """모든 엔드포인트가 비정상일 때"""
        strategy = RoundRobinStrategy()
        endpoints = self.create_endpoints(3)
        for ep in endpoints:
            ep.is_healthy = False
        
        assert strategy.select(endpoints) is None


class TestLoadBalancer:
    """LoadBalancer 테스트"""
    
    def test_balancer_creation(self):
        """로드밸런서 생성"""
        endpoints = [
            Endpoint(url="http://localhost:8000/v1"),
            Endpoint(url="http://localhost:8001/v1"),
        ]
        
        balancer = LoadBalancer(
            endpoints=endpoints,
            strategy=BalancingStrategy.ROUND_ROBIN,
            enable_health_check=False
        )
        
        assert len(balancer._endpoints) == 2
        balancer.close()
    
    def test_balancer_empty_endpoints_raises(self):
        """빈 엔드포인트 목록 시 예외"""
        with pytest.raises(ValueError):
            LoadBalancer(endpoints=[], enable_health_check=False)
    
    def test_add_remove_endpoint(self):
        """엔드포인트 추가/제거"""
        endpoints = [Endpoint(url="http://localhost:8000/v1")]
        balancer = LoadBalancer(
            endpoints=endpoints,
            enable_health_check=False
        )
        
        # 추가
        balancer.add_endpoint(Endpoint(url="http://localhost:8001/v1"))
        assert len(balancer._endpoints) == 2
        
        # 제거
        result = balancer.remove_endpoint("http://localhost:8001/v1")
        assert result == True
        assert len(balancer._endpoints) == 1
        
        # 존재하지 않는 엔드포인트 제거
        result = balancer.remove_endpoint("http://localhost:9999/v1")
        assert result == False
        
        balancer.close()
    
    def test_get_stats(self):
        """통계 조회"""
        endpoints = [
            Endpoint(url="http://localhost:8000/v1", name="EP-1"),
            Endpoint(url="http://localhost:8001/v1", name="EP-2"),
        ]
        balancer = LoadBalancer(
            endpoints=endpoints,
            strategy=BalancingStrategy.ROUND_ROBIN,
            enable_health_check=False
        )
        
        stats = balancer.get_stats()
        
        assert stats['strategy'] == 'round_robin'
        assert stats['total_endpoints'] == 2
        assert stats['healthy_endpoints'] == 2
        
        balancer.close()
    
    @patch('api_roadbalancer.balancer.requests.get')
    @patch('api_roadbalancer.balancer.requests.post')
    def test_chat_success(self, mock_post, mock_get):
        """chat 호출 성공"""
        # 모델 조회 mock
        mock_get.return_value.json.return_value = {
            'data': [{'id': 'test-model'}]
        }
        mock_get.return_value.raise_for_status = MagicMock()
        
        # chat 응답 mock
        mock_post.return_value.json.return_value = {
            'choices': [{
                'message': {
                    'content': 'Hello!',
                    'role': 'assistant'
                }
            }],
            'usage': {'total_tokens': 10}
        }
        mock_post.return_value.raise_for_status = MagicMock()
        
        endpoints = [Endpoint(url="http://localhost:8000/v1")]
        balancer = LoadBalancer(
            endpoints=endpoints,
            enable_health_check=False
        )
        
        result = balancer.chat(
            messages=[{"role": "user", "content": "Hi"}]
        )
        
        assert result['success'] == True
        assert result['content'] == 'Hello!'
        
        balancer.close()
    
    @patch('api_roadbalancer.balancer.requests.get')
    @patch('api_roadbalancer.balancer.requests.post')
    def test_chat_fallback_on_failure(self, mock_post, mock_get):
        """실패 시 다른 엔드포인트로 폴백"""
        # 모델 조회 mock
        mock_get.return_value.json.return_value = {
            'data': [{'id': 'test-model'}]
        }
        mock_get.return_value.raise_for_status = MagicMock()
        
        # 첫 번째 호출 실패, 두 번째 성공
        import requests
        mock_post.side_effect = [
            requests.Timeout(),
            MagicMock(
                json=MagicMock(return_value={
                    'choices': [{'message': {'content': 'OK'}}],
                    'usage': {}
                }),
                raise_for_status=MagicMock()
            )
        ]
        
        endpoints = [
            Endpoint(url="http://localhost:8000/v1", name="EP-1"),
            Endpoint(url="http://localhost:8001/v1", name="EP-2"),
        ]
        balancer = LoadBalancer(
            endpoints=endpoints,
            enable_health_check=False,
            retry_count=2
        )
        
        result = balancer.chat(
            messages=[{"role": "user", "content": "Hi"}]
        )
        
        assert result['success'] == True
        assert result['content'] == 'OK'
        
        balancer.close()
    
    def test_context_manager(self):
        """컨텍스트 매니저 지원"""
        endpoints = [Endpoint(url="http://localhost:8000/v1")]
        
        with LoadBalancer(endpoints=endpoints, enable_health_check=False) as balancer:
            assert len(balancer._endpoints) == 1
        # close가 호출되었는지는 헬스체커 상태로 간접 확인


class TestLoadBalancerFromEnv:
    """환경변수에서 로드 테스트"""
    
    @patch.dict('os.environ', {
        'LLM_ENDPOINTS': 'http://host1:8000/v1,http://host2:8000/v1',
        'LLM_API_KEYS': 'key1,key2',
        'LLM_WEIGHTS': '2,1',
        'LLM_STRATEGY': 'weighted',
        'LLM_HEALTH_CHECK': 'false',
    })
    def test_from_env(self):
        """환경변수에서 로드"""
        balancer = LoadBalancer.from_env()
        
        assert len(balancer._endpoints) == 2
        assert balancer._endpoints[0].endpoint.api_key == 'key1'
        assert balancer._endpoints[0].endpoint.weight == 2
        assert balancer._strategy_type == BalancingStrategy.WEIGHTED
        
        balancer.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
