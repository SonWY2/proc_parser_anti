# API Load Balancer (api_roadbalancer)

여러 OpenAI 호환 API 엔드포인트(vLLM, OpenAI 등)에 대해 요청을 분산시키는 로드밸런서 모듈입니다.

## 주요 기능

- **다중 엔드포인트 관리**: 여러 API 서버 등록 및 관리
- **로드밸런싱 전략**: Round Robin, Weighted, Least Connections, Random
- **헬스 체크**: 주기적 상태 확인 및 자동 장애 우회
- **자동 재시도**: 실패 시 다른 엔드포인트로 자동 폴백
- **엔드포인트별 설정**: max_tokens, temperature를 엔드포인트별로 설정 가능

---

## 기본 사용법

```python
from api_roadbalancer import LoadBalancer, Endpoint, BalancingStrategy

# 엔드포인트 정의
endpoints = [
    Endpoint(
        url="http://gpu1:8000/v1",
        weight=2,
        name="GPU-1",
        max_tokens=8192,
        temperature=0.7
    ),
    Endpoint(
        url="http://gpu2:8000/v1",
        weight=1,
        name="GPU-2",
        max_tokens=4096,
        temperature=0.5
    ),
]

# 로드밸런서 생성
balancer = LoadBalancer(
    endpoints=endpoints,
    strategy=BalancingStrategy.WEIGHTED,
    enable_health_check=True
)

# API 호출 (기존 LLMClient와 동일한 인터페이스)
response = balancer.chat(
    messages=[{"role": "user", "content": "Hello!"}]
)

if response['success']:
    print(response['content'])
    print(f"사용된 엔드포인트: {response['endpoint']}")
else:
    print(f"오류: {response['error']}")

# 리소스 정리
balancer.close()
```

---

## 환경변수에서 로드

```bash
export LLM_ENDPOINTS="http://gpu1:8000/v1,http://gpu2:8000/v1"
export LLM_API_KEYS="key1,key2"
export LLM_STRATEGY="round_robin"
export LLM_HEALTH_CHECK="true"
export LLM_TIMEOUT="60"
```

```python
balancer = LoadBalancer.from_env()
```

---

## 설정 파일 사용

### config.yaml

```yaml
strategy: weighted
timeout: 60
retry_count: 2
fallback_on_failure: true

health_check:
  enabled: true
  interval: 30

endpoints:
  - url: http://gpu1:8000/v1
    weight: 2
    name: GPU-1
    max_tokens: 8192
    temperature: 0.7
  - url: http://gpu2:8000/v1
    weight: 1
    name: GPU-2
    max_tokens: 4096
    temperature: 0.5
```

```python
balancer = LoadBalancer.from_config("config.yaml")
```

---

## 로드밸런싱 전략

| 전략 | 설명 |
|------|------|
| `ROUND_ROBIN` | 순차적으로 각 엔드포인트에 분배 |
| `WEIGHTED` | 가중치에 비례하여 분배 (weight=2는 2배 요청) |
| `LEAST_CONNECTIONS` | 현재 연결이 가장 적은 엔드포인트 선택 |
| `RANDOM` | 정상 엔드포인트 중 무작위 선택 |

---

## 통계 조회

```python
stats = balancer.get_stats()
print(stats)
# {
#     'strategy': 'weighted',
#     'total_endpoints': 2,
#     'healthy_endpoints': 2,
#     'total_requests': 100,
#     'total_success': 98,
#     'total_failures': 2,
#     'success_rate': '98.00%',
#     'endpoints': [...]
# }
```

---

## Context Manager 지원

```python
with LoadBalancer.from_config("config.yaml") as balancer:
    response = balancer.chat(messages=[...])
# 자동으로 close() 호출
```
