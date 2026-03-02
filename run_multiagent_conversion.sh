#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

HEADERS="tests/fixtures/sample_input_data/sample.h"
PROCS="tests/fixtures/sample_input_data/cursor_sample.pc"
OUTPUT="output/manual_run"
STRATEGY="preserve"
KNOWLEDGE=""

MODE="mock"
VLLM_ENDPOINT="${VLLM_API_ENDPOINT:-http://localhost:8000/v1}"
VLLM_MODEL_NAME="${VLLM_MODEL:-mock-model}"
VLLM_KEY="${VLLM_API_KEY:-${OPENAI_API_KEY:-}}"
HOOK_TARGET="tests.debug.vllm_hook:fake_java_response"
HOOK_LOG="output/hook_debug/hook_log.jsonl"

usage() {
  cat <<'EOF'
Usage:
  bash run_multiagent_conversion.sh [options]

Options:
  --headers <paths>      Comma-separated header file paths
  --procs <paths>        Comma-separated Pro*C file paths
  --output <dir>         Output directory (default: output/manual_run)
  --strategy <value>     preserve | refactor (default: preserve)
  --knowledge <path>     Optional knowledge markdown/doc path

  --mock                 Run in mock mode (default)
  --real                 Run with real vLLM endpoint
  --hook                 Run with local hook injection mode

  --endpoint <url>       vLLM API endpoint (for --real)
  --model <name>         vLLM model name (for --real/--hook)
  --api-key <key>        Optional API key (for --real)
  --hook-target <m:f>    Hook target module:function (for --hook)
  --hook-log <path>      Hook JSONL log path (for --hook)

  -h, --help             Show this help

Examples:
  bash run_multiagent_conversion.sh
  bash run_multiagent_conversion.sh --real --endpoint http://localhost:8000/v1 --model qwen2.5-coder
  bash run_multiagent_conversion.sh --strategy refactor --output output/refactor_run
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --headers)
      HEADERS="$2"
      shift 2
      ;;
    --procs)
      PROCS="$2"
      shift 2
      ;;
    --output)
      OUTPUT="$2"
      shift 2
      ;;
    --strategy)
      STRATEGY="$2"
      shift 2
      ;;
    --knowledge)
      KNOWLEDGE="$2"
      shift 2
      ;;
    --mock)
      MODE="mock"
      shift
      ;;
    --real)
      MODE="real"
      shift
      ;;
    --hook)
      MODE="hook"
      shift
      ;;
    --endpoint)
      VLLM_ENDPOINT="$2"
      shift 2
      ;;
    --model)
      VLLM_MODEL_NAME="$2"
      shift 2
      ;;
    --api-key)
      VLLM_KEY="$2"
      shift 2
      ;;
    --hook-target)
      HOOK_TARGET="$2"
      shift 2
      ;;
    --hook-log)
      HOOK_LOG="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ "$STRATEGY" != "preserve" && "$STRATEGY" != "refactor" ]]; then
  echo "ERROR: --strategy must be preserve or refactor" >&2
  exit 1
fi

IFS=',' read -r -a header_arr <<< "$HEADERS"
IFS=',' read -r -a proc_arr <<< "$PROCS"

for p in "${header_arr[@]}" "${proc_arr[@]}"; do
  trimmed="$(echo "$p" | xargs)"
  if [[ ! -f "$ROOT_DIR/$trimmed" && ! -f "$trimmed" ]]; then
    echo "ERROR: input file not found: $trimmed" >&2
    exit 1
  fi
done

mkdir -p "$ROOT_DIR/$OUTPUT"

unset VLLM_HOOK_TARGET VLLM_HOOK_LOG
case "$MODE" in
  mock)
    export VLLM_MOCK=true
    export VLLM_MODEL="$VLLM_MODEL_NAME"
    ;;
  real)
    export VLLM_MOCK=false
    export VLLM_API_ENDPOINT="$VLLM_ENDPOINT"
    export VLLM_MODEL="$VLLM_MODEL_NAME"
    if [[ -n "$VLLM_KEY" ]]; then
      export VLLM_API_KEY="$VLLM_KEY"
    fi
    ;;
  hook)
    export VLLM_MOCK=false
    export VLLM_MODEL="$VLLM_MODEL_NAME"
    export VLLM_HOOK_TARGET="$HOOK_TARGET"
    export VLLM_HOOK_LOG="$HOOK_LOG"
    ;;
  *)
    echo "ERROR: unknown mode: $MODE" >&2
    exit 1
    ;;
esac

cmd=(
  python "$ROOT_DIR/run_multiagent_conversion.py"
  --headers "$HEADERS"
  --procs "$PROCS"
  --output "$OUTPUT"
  --strategy "$STRATEGY"
)

if [[ -n "$KNOWLEDGE" ]]; then
  cmd+=(--knowledge "$KNOWLEDGE")
fi

echo "[run] mode=$MODE"
echo "[run] headers=$HEADERS"
echo "[run] procs=$PROCS"
echo "[run] output=$OUTPUT"
echo "[run] strategy=$STRATEGY"
if [[ "$MODE" == "real" ]]; then
  echo "[run] endpoint=$VLLM_ENDPOINT"
  echo "[run] model=$VLLM_MODEL_NAME"
fi
if [[ "$MODE" == "hook" ]]; then
  echo "[run] hook_target=$HOOK_TARGET"
  echo "[run] hook_log=$HOOK_LOG"
fi

"${cmd[@]}"

echo "[done] result: $OUTPUT/conversion_result.json"
