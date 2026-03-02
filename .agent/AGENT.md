# Agent Instructions

이 프로젝트에서 작업할 때 다음 지침을 따르세요.

## 1. 언어 규칙

- **유저와의 소통은 반드시 한글로 수행합니다.**

## 2. 로깅 규칙

- **로깅은 반드시 `loguru`를 사용합니다.**
- `print()` 또는 표준 `logging` 모듈 대신 `loguru`를 사용하세요.

```python
from loguru import logger

logger.info("작업 시작")
logger.debug("디버그 정보: {}", data)
logger.error("에러 발생: {}", error)
```

## 3. Magic Number 금지

- **절대로 임의의 매직 넘버를 사용하지 마세요.**
- 불명확한 상수값은 반드시 유저와 소통하여 정확한 로직으로 구현합니다.

### ❌ 금지 예시
```python
prompt[:100]  # 왜 100인가?
time.sleep(5)  # 왜 5초인가?
if len(items) > 10:  # 왜 10인가?
```

### ✅ 올바른 예시
```python
# 설정 또는 상수로 정의
MAX_PROMPT_LENGTH = 100  # 유저와 합의한 값
RETRY_DELAY_SECONDS = 5  # 명시적 이유가 있는 값

prompt[:MAX_PROMPT_LENGTH]
time.sleep(RETRY_DELAY_SECONDS)
```

**매직 넘버가 필요한 상황이라면, 유저에게 질문하여 의도를 확인하세요.**

## 4. 모듈 문서화 규칙

- **모듈을 작성하면 반드시 `usage.md` 파일을 함께 작성합니다.**
- 모듈이 수정되면 `usage.md`도 함께 수정해야 합니다.
- `usage.md`에는 다음 내용을 포함합니다:
  - 모듈의 목적
  - 사용 예시 (코드 스니펫)
  - 주요 함수/클래스 설명
  - 의존성

## 5. 아키텍처 규칙

- `proc_parser/DEVELOPER_GUIDE.md`의 아키텍처 패턴과 규칙을 따르세요.
- Main Logic + Plugin 패턴을 준수합니다.
