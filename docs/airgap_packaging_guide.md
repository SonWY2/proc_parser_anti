# Ubuntu Air-gap 패키징 가이드

Python 바이너리가 없는 폐쇄망(air-gap) Ubuntu 환경에서 본 시스템을 실행하기 위한 패키징 절차입니다.

## 준비(인터넷 가능 빌드 머신)
- Ubuntu
- `curl`, `tar`, `rsync`, `python3`

## 패키징 실행
```bash
./scripts/package_airgap_ubuntu.sh
```

## 주의
- `source scripts/package_airgap_ubuntu.sh`로 실행하지 마세요.
- 반드시 아래처럼 실행 파일로 호출해야 합니다:
```bash
./scripts/package_airgap_ubuntu.sh
```


생성물:
- `dist/proc_parser_anti-airgap-<timestamp>.tar.gz`

## 폐쇄망 서버로 전달 후 실행
```bash
tar -xzf proc_parser_anti-airgap-<timestamp>.tar.gz
cd proc_parser_anti-airgap-<timestamp>
./scripts/healthcheck.sh
./scripts/run.sh \
  --headers app/tests/fixtures/sample_input_data/sample.h \
  --procs app/tests/fixtures/sample_input_data/cursor_sample.pc \
  --output output/airgap_run \
  --strategy preserve
```

## 커스터마이징
기본 내장 Python URL을 변경하려면:
```bash
PYTHON_STANDALONE_URL="<python-build-standalone tar.gz URL>" ./scripts/package_airgap_ubuntu.sh
```

## 정리
```bash
./scripts/package_airgap_ubuntu.sh --clean
```


## 다운로드 실패/재사용 시 로컬 아카이브 사용
```bash
PYTHON_STANDALONE_ARCHIVE_PATH=/path/to/cpython-standalone.tar.gz \
./scripts/package_airgap_ubuntu.sh
```

> 스크립트는 `python3`, `python3.11` 등 실행 가능한 바이너리를 자동 탐색합니다.


## 디버그 모드
실패 지점/실행 명령을 자세히 보려면:
```bash
AIRGAP_DEBUG=1 ./scripts/package_airgap_ubuntu.sh
```

실패 시 `[ERROR][<step>]` 형태로 단계명이 함께 출력됩니다.
