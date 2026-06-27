#Build chatML format 
#Train
#Validate
#merge adapters
#dowload llama.cpp and check if llama.quantise llama.imatrix, convert_to_gguf exists
#bash gguf_convert.sh
#python calibration.py
#bash quantize (if fails to find imatrix cp llama.cpp/build/bin/llama-* llama.cpp/)


# (ai_interview_platform) apoor@Arjun:~/projects/ai_interview_platform$ wc -c llama.cpp/calibration_data.txt
# 2521171 llama.cpp/calibration_data.txt
# (ai_interview_platform) apoor@Arjun:~/projects/ai_interview_platform$ head -c 250000 llama.cpp/calibration_data.txt > llama.cpp/calibration_data_small.txt
# (ai_interview_platform) apoor@Arjun:~/projects/ai_interview_platform$ bash quantize.sh finetune/gguf/model-f16.gguf llama.cpp/calibration_data_small.txt
# bash: quantize.sh: No such file or directory

# The imatrix's job is to estimate, per weight, "how much does this weight matter for typical outputs" by observing activations on a sample of representative text. Once you have a few hundred KB to a couple MB of reasonably representative text, more data gives rapidly diminishing returns — you're not meaningfully improving quantization quality by running all 815 examples through it instead of 100-150,
# ./llama.cpp/llama-cli -m finetune/gguf/model-Q4_K_M.gguf -p "Hello!"