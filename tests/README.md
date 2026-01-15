# Tests

테스트 파일 및 데이터 디렉토리 구조입니다.

## 📁 폴더 구조

```
tests/
├── unit/           # 단위 테스트 (개별 모듈/함수 테스트)
├── integration/    # 통합 테스트 (모듈 간 연동 테스트)
├── runners/        # 테스트 러너 및 CLI 도구
├── fixtures/       # 테스트 데이터
│   ├── samples/          # 샘플 Pro*C 코드
│   ├── sample_input/     # 추가 입력 샘플
│   ├── sample_input_data/ # 입력 데이터 (sample.pc 등)
│   └── *.json            # 메타데이터 JSON 파일
├── debug/          # 디버깅용 스크립트 및 출력
│   └── output/           # 디버그 출력
└── output/         # 테스트 실행 결과 (gitignore됨)
    ├── test_output/
    ├── test_output_cached/
    └── test_output_original_source/
```

## 🧪 테스트 실행

### 전체 테스트
```bash
python -m pytest tests/unit/
python -m pytest tests/integration/
```

### 개별 테스트
```bash
python -m pytest tests/unit/test_sql_extractor.py
python -m pytest tests/integration/test_connections.py
```

### 테스트 러너 사용
```bash
python tests/runners/test_runner.py
python tests/runners/proc_test_runner.py
```

## 📂 주요 파일

| 위치 | 설명 |
|------|------|
| `unit/test_*.py` | 각 모듈별 단위 테스트 |
| `integration/test_connections.py` | 외부 연결(Neo4j 등) 테스트 |
| `runners/legacy_input_test.py` | CLI 기반 SQL 추출 테스트 |
| `fixtures/samples/` | 테스트용 Pro*C 샘플 파일들 |
