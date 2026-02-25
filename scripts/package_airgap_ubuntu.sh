#!/usr/bin/env bash
set -euo pipefail

if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  echo "[ERROR] Do not source this script. Run it as: ./scripts/package_airgap_ubuntu.sh" >&2
  return 1 2>/dev/null || exit 1
fi

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
PYTHON_STANDALONE_ARCHIVE_PATH="${PYTHON_STANDALONE_ARCHIVE_PATH:-}"
AIRGAP_DEBUG="${AIRGAP_DEBUG:-0}"

# Requirements needed for run_multiagent_conversion.py + agents pipeline
REQ_FILES=(
  "infra/agents/langchain/requirements.txt"
  "parsing/core/requirements.txt"
  "parsing/sql/requirements.txt"
  "conversion/requirements.txt"
  "generation/merge/requirements.txt"
)

CURRENT_STEP="init"

log_info() {
  echo "[INFO][${CURRENT_STEP}] $*"
}

log_debug() {
  if [[ "$AIRGAP_DEBUG" == "1" || "$AIRGAP_DEBUG" == "true" ]]; then
    echo "[DEBUG][${CURRENT_STEP}] $*"
  fi
}

log_error() {
  echo "[ERROR][${CURRENT_STEP}] $*" >&2
}

set_step() {
  CURRENT_STEP="$1"
  echo "[STEP] ${CURRENT_STEP}"
}

on_error() {
  local line_no="$1"
  local cmd="$2"
  local code="$3"

  log_error "failed at line=${line_no}, exit_code=${code}"
  log_error "last command: ${cmd}"

  if [[ -d "$BUNDLE_DIR/runtime" ]]; then
    log_error "runtime dir snapshot (maxdepth=4):"
    find "$BUNDLE_DIR/runtime" -maxdepth 4 -type d | sed 's#^#  - #' >&2 || true
  fi
}
trap 'on_error "$LINENO" "$BASH_COMMAND" "$?"' ERR

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--clean]

Environment variables:
  PYTHON_STANDALONE_URL          URL of python-build-standalone archive
  PYTHON_STANDALONE_ARCHIVE_PATH local tar.gz path (skip download)
  AIRGAP_DEBUG                   1/true면 디버그 로그 출력

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
    log_error "required command missing: $1"
    exit 1
  }
}

resolve_python_bin() {
  local runtime_dir="$1"
  local candidate

  # Common python-build-standalone layouts
  for candidate in \
    "$runtime_dir/python/install/bin/python3" \
    "$runtime_dir/install/bin/python3" \
    "$runtime_dir/bin/python3" \
    "$runtime_dir/python/install/bin/python" \
    "$runtime_dir/install/bin/python" \
    "$runtime_dir/bin/python"; do
    if [[ -x "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done

  # Fallback: find python3/python3.* or plain python (permission bit may be missing in some archives)
  candidate="$(find "$runtime_dir" -type f \( -name 'python3' -o -name 'python3.*' -o -name 'python' \) | head -n 1 || true)"
  if [[ -n "$candidate" ]]; then
    echo "$candidate"
    return 0
  fi

  return 1
}

set_step "preflight"
need_cmd tar
need_cmd rsync
need_cmd python3
need_cmd find

mkdir -p "$WORK_DIR" "$DIST_DIR"
rm -rf "$BUNDLE_DIR"
mkdir -p "$BUNDLE_DIR"/{runtime,wheelhouse,app,scripts}

set_step "download_python"
if [[ -n "$PYTHON_STANDALONE_ARCHIVE_PATH" ]]; then
  log_info "Using local standalone Python archive: $PYTHON_STANDALONE_ARCHIVE_PATH"
  cp "$PYTHON_STANDALONE_ARCHIVE_PATH" "$PYTHON_STANDALONE_ARCHIVE"
else
  need_cmd curl
  log_info "Downloading standalone Python from: $PYTHON_STANDALONE_URL"
  curl -fL "$PYTHON_STANDALONE_URL" -o "$PYTHON_STANDALONE_ARCHIVE"
fi

set_step "extract_python"
log_info "Extracting archive: $PYTHON_STANDALONE_ARCHIVE"
tar -xzf "$PYTHON_STANDALONE_ARCHIVE" -C "$BUNDLE_DIR/runtime"

log_debug "Listing extracted python-like binaries"
find "$BUNDLE_DIR/runtime" -type f \( -name 'python' -o -name 'python3' -o -name 'python3.*' \) | sed 's#^#  - #' || true

set_step "resolve_runtime_python"
PY_BIN="$(resolve_python_bin "$BUNDLE_DIR/runtime" || true)"
if [[ -z "$PY_BIN" ]]; then
  log_error "python binary not found after extraction"
  exit 1
fi

chmod +x "$PY_BIN"
log_info "runtime python resolved: $PY_BIN"

set_step "create_venv"
"$PY_BIN" -m venv "$BUNDLE_DIR/runtime/venv"
VENV_PIP="$BUNDLE_DIR/runtime/venv/bin/pip"
"$VENV_PIP" install --upgrade pip setuptools wheel

set_step "build_wheelhouse"
COMBINED_REQ="$WORK_DIR/combined_requirements.txt"
: > "$COMBINED_REQ"
for req in "${REQ_FILES[@]}"; do
  if [[ -f "$ROOT_DIR/$req" ]]; then
    log_debug "append requirements: $req"
    cat "$ROOT_DIR/$req" >> "$COMBINED_REQ"
    echo >> "$COMBINED_REQ"
  else
    log_debug "skip missing requirements file: $req"
  fi
done

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
p.write_text("\n".join(seen) + "\n", encoding="utf-8")
print(f"[INFO][build_wheelhouse] deduplicated requirements: {len(seen)}")
PY

"$VENV_PIP" wheel -r "$COMBINED_REQ" -w "$BUNDLE_DIR/wheelhouse"

set_step "install_offline_deps"
"$VENV_PIP" install --no-index --find-links "$BUNDLE_DIR/wheelhouse" -r "$COMBINED_REQ"

set_step "copy_sources"
rsync -a "$ROOT_DIR/" "$BUNDLE_DIR/app/" \
  --exclude '.git' \
  --exclude '.airgap_build' \
  --exclude 'dist' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude 'output'

set_step "write_launchers"
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

set_step "pack_bundle"
TARBALL_PATH="$DIST_DIR/${BUNDLE_NAME}.tar.gz"
tar -czf "$TARBALL_PATH" -C "$WORK_DIR" "$BUNDLE_NAME"

set_step "done"
log_info "bundle created: $TARBALL_PATH"
