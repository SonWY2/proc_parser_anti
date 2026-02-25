# LangGraph 멀티에이전트 변환 실행 가이드

이 문서는 현재 구현된 `run_multiagent_conversion.py` 기준의 **실행/디버깅 방법**을 정리합니다.

## 1) 기본 실행

```bash
python run_multiagent_conversion.py \
  --headers tests/fixtures/sample_input_data/sample.h \
  --procs tests/fixtures/sample_input_data/cursor_sample.pc \
  --output output/langgraph_run \
  --strategy preserve
```

실행 완료 후 주요 산출물:

- `output/langgraph_run/java/service/*.java`
- `output/langgraph_run/mybatis/mapper/*.xml`
- `output/langgraph_run/report/migration-report.md`
- `output/langgraph_run/conversion_result.json`

---

## 2) vLLM 실제 호출 모드

`VLLM_MOCK=false`로 설정하면 OpenAI 호환 엔드포인트(`/chat/completions`)를 호출합니다.

```bash
export VLLM_MOCK=false
export VLLM_API_ENDPOINT=http://<vllm-host>:8000/v1
export VLLM_MODEL=<model-name>
export VLLM_API_KEY=<optional-api-key>
```

그 다음 기본 실행 명령을 동일하게 실행합니다.

---

## 3) 네트워크 없이 호출 경로 디버깅 (Hooking)

외부 mocking 인프라 없이도, 실제 호출 직전 payload를 훅 함수로 주입해 결과를 받을 수 있습니다.

### 3-1. Hook 모드 실행

```bash
VLLM_MOCK=false \
VLLM_HOOK_TARGET=tests.debug.vllm_hook:fake_java_response \
VLLM_HOOK_LOG=output/hook_debug/hook_log.jsonl \
VLLM_MODEL=debug-model \
python run_multiagent_conversion.py \
  --headers tests/fixtures/sample_input_data/sample.h \
  --procs tests/fixtures/sample_input_data/cursor_sample.pc \
  --output output/hook_debug \
  --strategy preserve
```

### 3-2. 확인 포인트

```bash
# Hook 응답이 Java 파일에 반영되었는지
sed -n '1,80p' output/hook_debug/java/service/CursorSampleService.java

# 실제 payload/preview 로그
sed -n '1,5p' output/hook_debug/hook_log.jsonl
```

---

## 4) 환경변수 요약

- `VLLM_MOCK` : `true`(기본) / `false`
- `VLLM_API_ENDPOINT` : vLLM OpenAI-compatible endpoint
- `VLLM_MODEL` : 호출 모델명
- `VLLM_API_KEY` : 필요 시 인증키
- `VLLM_HOOK_TARGET` : `module:function` 형식 훅 함수
- `VLLM_HOOK_LOG` : 훅 호출 로그(JSONL) 파일 경로

---

## 5) 트러블슈팅

### `langgraph` 패키지가 없어도 실행되나요?
네. 현재 구현은 `langgraph` 미설치 시 내부 순차 fallback 그래프로 동작합니다.

### `VLLM_HOOK_TARGET` 포맷 오류
`module:function` 형식이 아니면 예외가 발생합니다.

### 실행 종료 코드
- `0`: 정상 완료(에러 없음)
- `2`: 산출물은 생성됐지만 `errors` 존재
- `1`: 예외로 실행 실패(런타임 에러)


## Air-gap 패키징

- Ubuntu 폐쇄망 배포용 패키징은 `docs/airgap_packaging_guide.md`를 참고하세요.
