# Ubuntu Air-gap 패키징 가이드

Python 바이너리가 없는 폐쇄망(air-gap) Ubuntu 환경에서 본 시스템을 실행하기 위한 패키징 절차입니다.

## 준비(인터넷 가능 빌드 머신)
- Ubuntu
- `curl`, `tar`, `rsync`, `python3`

## 패키징 실행
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
