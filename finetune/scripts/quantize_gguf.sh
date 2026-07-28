#!/bin/bash
# quantize.sh - Run imatrix calibration pass, then quantize to Q4_K_M.
# CPU-bound (uses GPU if llama.cpp was built with CUDA and one is
# available, but works fine without).
#
# Usage: ./quantize.sh <f16_gguf_path> [calibration_data_path]
# Example: ./quantize.sh finetune/gguf/model-f16.gguf llama.cpp/calibration_data.txt

set -e

F16_GGUF="${1:-finetune/gguf/model-retrain-f16.gguf}"
CALIBRATION_DATA="${2:-llama.cpp/calibration_data.txt}"
OUT_DIR="$(dirname "$F16_GGUF")"
IMATRIX_OUT="$OUT_DIR/imatrix.dat"
Q4_OUT="$OUT_DIR/model-retrain-Q4_K_M.gguf"

if [ ! -f "$CALIBRATION_DATA" ]; then
    echo "Calibration data not found at $CALIBRATION_DATA"
    echo "Run: python build_calibration_data.py first, or pass a path explicitly."
    exit 1
fi

echo "Running imatrix calibration pass..."
./llama.cpp/llama-imatrix \
    -m "$F16_GGUF" \
    -f "$CALIBRATION_DATA" \
    -o "$IMATRIX_OUT"

echo "Quantizing to Q4_K_M with imatrix..."
./llama.cpp/llama-quantize \
    --imatrix "$IMATRIX_OUT" \
    "$F16_GGUF" \
    "$Q4_OUT" \
    Q4_K_M

echo "Quantization complete: $Q4_OUT"
echo "Test it with: ./llama.cpp/llama-cli -m $Q4_OUT -p \"Hello!\""