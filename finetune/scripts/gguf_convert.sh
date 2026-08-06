# #!/bin/bash
# # setup_llama_cpp.sh - One-time build of llama.cpp.
# # Run this once. CPU-bound build process - works on Kaggle (GPU not
# # required for the build itself, though -DGGML_CUDA=ON lets the resulting
# # binaries use a GPU later if present) or locally.
# #
# # Commands below match Unsloth's current official documentation
# # (docs as of May 2026) for building llama.cpp from source.

# set -e  # stop on first error

# apt-get update
# apt-get install -y pciutils build-essential cmake curl libcurl4-openssl-dev

# if [ ! -d "llama.cpp" ]; then
#     git clone https://github.com/ggml-org/llama.cpp
# fi

# # -DGGML_CUDA=ON: build with GPU support (harmless to include even if you
# #   end up running quantization on CPU only - the binaries will just not
# #   use CUDA if none is available at runtime)
# # -DLLAMA_CURL=ON: needed for some download-related features; if this
# #   causes build issues in your environment, switch to OFF (you don't need
# #   it for local merge/convert/quantize)
# cmake llama.cpp -B llama.cpp/build \
#     -DBUILD_SHARED_LIBS=OFF -DGGML_CUDA=ON -DLLAMA_CURL=ON

# cmake --build llama.cpp/build --config Release -j \
#     --clean-first --target llama-cli llama-mtmd-cli llama-server llama-gguf-split llama-quantize llama-imatrix

# # Copy binaries to a convenient flat location
# cp llama.cpp/build/bin/llama-* llama.cpp/

# # Install the Python requirements needed for convert_hf_to_gguf.py
# pip install -r llama.cpp/requirements.txt

# echo "llama.cpp build complete."
# echo "Binaries available at: llama.cpp/llama-quantize, llama.cpp/llama-imatrix, etc."


# set -e
 
# MERGED_MODEL_DIR="${1:-finetune/merged/merged_model_v2}"
# OUTPUT_GGUF="${2:-finetune/gguf/model-f16.gguf}"
 
# mkdir -p "$(dirname "$OUTPUT_GGUF")"
 
# python llama.cpp/convert_hf_to_gguf.py \
#     "$MERGED_MODEL_DIR" \
#     --outfile "$OUTPUT_GGUF" \
#     --outtype f16
 
# echo "GGUF conversion complete: $OUTPUT_GGUF"
# echo "Next: ./quantize.sh $OUTPUT_GGUF"
 

#After fixing EOS
set -e
 
MERGED_MODEL_DIR="${1:-finetune/merged/merged_model_with_eos}"
OUTPUT_GGUF="${2:-finetune/gguf/model-retrain-f16.gguf}"
 
mkdir -p "$(dirname "$OUTPUT_GGUF")"
 
python llama.cpp/convert_hf_to_gguf.py \
    "$MERGED_MODEL_DIR" \
    --outfile "$OUTPUT_GGUF" \
    --outtype f16
 
echo "GGUF conversion complete: $OUTPUT_GGUF"
echo "Next: ./quantize.sh $OUTPUT_GGUF"
 