#!/usr/bin/env bash
set -euo pipefail

# Build an Ubuntu air-gap runnable bundle for this repository.
# Result: dist/proc_parser_anti-airgap-<timestamp>.tar.gz

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${ROOT_DIR}/dist"
WORK_DIR="${ROOT_DIR}/.airgap_build"
TS="$(date +%Y%m%d_%H%M%S)"
BUNDLE_NAME="proc_parser_anti-airgap-${TS}"
BUNDLE_DIR="${WORK_DIR}/${BUNDLE_NAME}"

PYTHON_STANDALONE_URL_DEFAULT="https://github.com/astral-sh/python-build-standalone/releases/download/20250205/cpython-3.11.11%2B20250205-x86_64-unknown-linux-gnu-install_only.tar.gz"
PYTHON_STANDALONE_URL="${PYTHON_STANDALONE_URL:-$PYTHON_STANDALONE_URL_DEFAULT}"
PYTHON_STANDALONE_ARCHIVE="${WORK_DIR}/python-standalone.tar.gz"

# Requirements needed for run_multiagent_conversion.py + agents pipeline
REQ_FILES=(
  "infra/agents/langchain/requirements.txt"
  "parsing/core/requirements.txt"
  "parsing/sql/requirements.txt"
  "conversion/requirements.txt"
  "generation/merge/requirements.txt"
)

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--clean]

Environment variables:
  PYTHON_STANDALONE_URL   URL of python-build-standalone archive

Output:
  dist/<bundle>.tar.gz
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ "${1:-}" == "--clean" ]]; then
  rm -rf "$WORK_DIR" "$DIST_DIR"/proc_parser_anti-airgap-*.tar.gz
  echo "[OK] cleaned previous build artifacts"
  exit 0
fi

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "[ERROR] required command missing: $1" >&2
    exit 1
  }
}

need_cmd curl
need_cmd tar
need_cmd rsync
need_cmd python3

mkdir -p "$WORK_DIR" "$DIST_DIR"
rm -rf "$BUNDLE_DIR"
mkdir -p "$BUNDLE_DIR"/{runtime,wheelhouse,app,scripts}

echo "[1/7] Downloading standalone Python..."
curl -fL "$PYTHON_STANDALONE_URL" -o "$PYTHON_STANDALONE_ARCHIVE"

echo "[2/7] Extracting standalone Python..."
tar -xzf "$PYTHON_STANDALONE_ARCHIVE" -C "$BUNDLE_DIR/runtime"

PY_BIN="$(find "$BUNDLE_DIR/runtime" -type f -name 'python3' | head -n 1 || true)"
if [[ -z "$PY_BIN" ]]; then
  echo "[ERROR] python3 binary not found after extraction" >&2
  exit 1
fi

chmod +x "$PY_BIN"

echo "[3/7] Creating embedded virtualenv..."
"$PY_BIN" -m venv "$BUNDLE_DIR/runtime/venv"
VENV_PY="$BUNDLE_DIR/runtime/venv/bin/python"
VENV_PIP="$BUNDLE_DIR/runtime/venv/bin/pip"

"$VENV_PIP" install --upgrade pip setuptools wheel

echo "[4/7] Building offline wheelhouse..."
COMBINED_REQ="$WORK_DIR/combined_requirements.txt"
: > "$COMBINED_REQ"
for req in "${REQ_FILES[@]}"; do
  if [[ -f "$ROOT_DIR/$req" ]]; then
    cat "$ROOT_DIR/$req" >> "$COMBINED_REQ"
    echo >> "$COMBINED_REQ"
  fi
done
# remove comments/blanks/duplicates
python3 - <<PY
from pathlib import Path
p = Path("$COMBINED_REQ")
lines = [l.strip() for l in p.read_text(encoding="utf-8").splitlines()]
seen = []
for l in lines:
    if not l or l.startswith('#'):
        continue
    if l not in seen:
        seen.append(l)
p.write_text("\n".join(seen)+"\n", encoding="utf-8")
PY

"$VENV_PIP" wheel -r "$COMBINED_REQ" -w "$BUNDLE_DIR/wheelhouse"

echo "[5/7] Installing dependencies from local wheelhouse..."
"$VENV_PIP" install --no-index --find-links "$BUNDLE_DIR/wheelhouse" -r "$COMBINED_REQ"

echo "[6/7] Copying application sources..."
rsync -a "$ROOT_DIR/" "$BUNDLE_DIR/app/" \
  --exclude '.git' \
  --exclude '.airgap_build' \
  --exclude 'dist' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude 'output'

cat > "$BUNDLE_DIR/scripts/run.sh" <<'RUNEOF'
#!/usr/bin/env bash
set -euo pipefail
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
"$BASE_DIR/runtime/venv/bin/python" "$BASE_DIR/app/run_multiagent_conversion.py" "$@"
RUNEOF
chmod +x "$BUNDLE_DIR/scripts/run.sh"

cat > "$BUNDLE_DIR/scripts/healthcheck.sh" <<'CHECKEOF'
#!/usr/bin/env bash
set -euo pipefail
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
"$BASE_DIR/runtime/venv/bin/python" -V
"$BASE_DIR/runtime/venv/bin/python" -c "import requests; print('healthcheck: ok')"
CHECKEOF
chmod +x "$BUNDLE_DIR/scripts/healthcheck.sh"

cat > "$BUNDLE_DIR/README_AIRGAP.md" <<'READEOF'
# Air-gap 실행 가이드 (Ubuntu)

## 1) 압축 해제
```bash
tar -xzf proc_parser_anti-airgap-*.tar.gz
cd proc_parser_anti-airgap-*
```

## 2) 런타임 확인 (python 바이너리 없어도 됨)
```bash
./scripts/healthcheck.sh
```

## 3) 파이프라인 실행
```bash
./scripts/run.sh \
  --headers app/tests/fixtures/sample_input_data/sample.h \
  --procs app/tests/fixtures/sample_input_data/cursor_sample.pc \
  --output output/airgap_run \
  --strategy preserve
```
READEOF

echo "[7/7] Packing tarball..."
TARBALL_PATH="$DIST_DIR/${BUNDLE_NAME}.tar.gz"
tar -czf "$TARBALL_PATH" -C "$WORK_DIR" "$BUNDLE_NAME"

echo "[DONE] $TARBALL_PATH"
