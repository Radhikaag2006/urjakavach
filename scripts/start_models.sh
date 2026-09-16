#!/usr/bin/env bash
# Start both llama.cpp model servers (Mac / Linux).
#
# Usage:
#   ./scripts/start_models.sh /path/to/models
#
# Leaves both servers running in the background. Stop them with:
#   pkill -f llama-server

set -e

MODEL_DIR="${1:-./models}"

REASONING_MODEL="$MODEL_DIR/Llama-3.2-3B-Instruct-Q4_K_M.gguf"
CODE_MODEL="$MODEL_DIR/Qwen2.5-Coder-1.5B-Instruct-Q4_K_M.gguf"

if ! command -v llama-server >/dev/null 2>&1; then
  echo "ERROR: llama-server not found."
  echo "  Mac:   brew install llama.cpp"
  echo "  Linux: build from source or use a release binary"
  exit 1
fi

for m in "$REASONING_MODEL" "$CODE_MODEL"; do
  if [ ! -f "$m" ]; then
    echo "ERROR: model file not found: $m"
    echo "Download the GGUF files listed in docs/SETUP.md into $MODEL_DIR"
    exit 1
  fi
done

# Prevent duplicate model processes from competing for CPU and memory.
pkill -f 'llama-server.*--port 8080' 2>/dev/null || true
pkill -f 'llama-server.*--port 8081' 2>/dev/null || true

echo "Starting reasoning model on :8080 ..."
llama-server -m "$REASONING_MODEL" --port 8080 --ctx-size 3072 --threads 4 --threads-batch 4 --parallel 1 --n-gpu-layers 0 > /tmp/llama_reasoning.log 2>&1 &

echo "Starting code model on :8081 ..."
llama-server -m "$CODE_MODEL" --port 8081 --ctx-size 3072 --threads 4 --threads-batch 4 --parallel 1 --n-gpu-layers 0 > /tmp/llama_code.log 2>&1 &

sleep 5
echo ""
echo "Health checks:"
curl -s http://localhost:8080/health && echo " <- reasoning (8080)"
curl -s http://localhost:8081/health && echo " <- code (8081)"
echo ""
echo "Now set USE_REAL_MODEL=true in your .env and restart the backend."
