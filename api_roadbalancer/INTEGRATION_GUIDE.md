# 커스텀 LLM 클래스 통합 가이드

기존 커스텀 LLM 클래스에 로드밸런서를 통합하는 방법을 설명합니다.

---

## 가정: 기존 커스텀 LLM 클래스

```python
# 가정: 사용자의 기존 LLM 클래스 (예시)
class CustomLLM:
    def __init__(self, endpoint: str, api_key: str = None):
        self.endpoint = endpoint
        self.api_key = api_key
        self.history = []  # 대화 히스토리
    
    def chat(self, message: str, **kwargs) -> str:
        # 히스토리에 추가하고 API 호출
        self.history.append({"role": "user", "content": message})
        response = self._call_api(message, **kwargs)
        self.history.append({"role": "assistant", "content": response})
        return response
    
    def _call_api(self, message: str, **kwargs) -> str:
        # 실제 API 호출 로직
        pass
    
    def clear_history(self):
        self.history = []
```

---

## 방법 1: Wrapper 패턴 (권장)

기존 인터페이스를 그대로 유지하면서 내부에서 로드밸런서를 사용합니다.

```python
from api_roadbalancer import LoadBalancer, Endpoint, BalancingStrategy

class BalancedLLM:
    """기존 CustomLLM의 인터페이스를 유지하면서 로드밸런싱 적용"""
    
    def __init__(
        self, 
        endpoints: list[Endpoint], 
        strategy: BalancingStrategy = BalancingStrategy.ROUND_ROBIN
    ):
        self.balancer = LoadBalancer(
            endpoints=endpoints,
            strategy=strategy,
            enable_health_check=True
        )
        self.history = []  # 기존 히스토리 기능 유지
    
    def chat(self, message: str, **kwargs) -> str:
        """기존 CustomLLM.chat()과 동일한 인터페이스"""
        # 히스토리에 사용자 메시지 추가
        self.history.append({"role": "user", "content": message})
        
        # 로드밸런서를 통해 API 호출
        response = self.balancer.chat(
            messages=self.history,  # 전체 히스토리 전달
            temperature=kwargs.get('temperature'),
            max_tokens=kwargs.get('max_tokens')
        )
        
        if response['success']:
            content = response['content']
            self.history.append({"role": "assistant", "content": content})
            return content
        else:
            raise Exception(f"API 호출 실패: {response['error']}")
    
    def clear_history(self):
        self.history = []
    
    def get_stats(self):
        """로드밸런서 통계 조회 (추가 기능)"""
        return self.balancer.get_stats()
    
    def close(self):
        self.balancer.close()
```

### 사용 예시

```python
llm = BalancedLLM(
    endpoints=[
        Endpoint(url="http://gpu1:8000/v1", weight=2, max_tokens=8192),
        Endpoint(url="http://gpu2:8000/v1", weight=1, max_tokens=4096),
    ],
    strategy=BalancingStrategy.WEIGHTED
)

# 기존과 동일하게 사용
response = llm.chat("안녕하세요!")
print(llm.history)  # 히스토리 확인
```

---

## 방법 2: 상속 + Override 패턴

기존 클래스를 상속받아 API 호출 부분만 오버라이드합니다.

```python
from api_roadbalancer import LoadBalancer, Endpoint

class BalancedCustomLLM(CustomLLM):
    """기존 CustomLLM을 상속하고 API 호출만 로드밸런싱으로 대체"""
    
    def __init__(self, endpoints: list[Endpoint], **kwargs):
        # 첫 번째 엔드포인트로 부모 클래스 초기화 (호환성)
        super().__init__(
            endpoint=endpoints[0].url,
            api_key=endpoints[0].api_key
        )
        
        # 로드밸런서 추가
        self._balancer = LoadBalancer(endpoints=endpoints, **kwargs)
    
    def _call_api(self, message: str, **kwargs) -> str:
        """API 호출 메서드만 오버라이드"""
        response = self._balancer.chat(
            messages=self.history + [{"role": "user", "content": message}],
            **kwargs
        )
        
        if response['success']:
            return response['content']
        raise Exception(response['error'])
```

### 사용 예시

```python
llm = BalancedCustomLLM(
    endpoints=[
        Endpoint(url="http://gpu1:8000/v1"),
        Endpoint(url="http://gpu2:8000/v1"),
    ]
)

# 기존 CustomLLM과 완전히 동일하게 사용
response = llm.chat("질문입니다")
```

---

## 방법 3: Dependency Injection 패턴

기존 클래스를 수정하지 않고, API 호출 함수를 주입합니다.

```python
from api_roadbalancer import LoadBalancer, Endpoint

# 로드밸런서를 callable로 만드는 팩토리
def create_balanced_api_caller(endpoints: list[Endpoint]) -> callable:
    balancer = LoadBalancer(endpoints=endpoints)
    
    def call_api(messages: list, **kwargs) -> str:
        response = balancer.chat(messages=messages, **kwargs)
        if response['success']:
            return response['content']
        raise Exception(response['error'])
    
    return call_api


# 기존 CustomLLM에서 api_caller를 주입받도록 수정
class CustomLLM:
    def __init__(self, api_caller: callable = None):
        self.api_caller = api_caller or self._default_caller
        self.history = []
    
    def chat(self, message: str, **kwargs) -> str:
        self.history.append({"role": "user", "content": message})
        response = self.api_caller(self.history, **kwargs)
        self.history.append({"role": "assistant", "content": response})
        return response
```

### 사용 예시

```python
balanced_caller = create_balanced_api_caller([
    Endpoint(url="http://gpu1:8000/v1"),
    Endpoint(url="http://gpu2:8000/v1"),
])
llm = CustomLLM(api_caller=balanced_caller)

response = llm.chat("Hello!")
```

---

## 방법 비교

| 패턴 | 기존 코드 수정 | 호환성 | 복잡도 | 권장 상황 |
|------|--------------|--------|--------|----------|
| Wrapper | 없음 | 높음 | 낮음 | 신규 코드 또는 교체 가능 시 |
| 상속 | 없음 | 완벽 | 중간 | 기존 클래스 유지 필요 시 |
| DI | 약간 | 높음 | 높음 | 테스트/유연성 중요 시 |

---

## 권장사항

기존 코드 수정을 최소화하려면 **방법 1 (Wrapper 패턴)**을 권장합니다:

- 기존 인터페이스를 100% 호환
- 히스토리 등 기존 기능 보존
- 로드밸런서 통계 등 추가 기능 제공 가능
- 테스트 및 디버깅 용이
