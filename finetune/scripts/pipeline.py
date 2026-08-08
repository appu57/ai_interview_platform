#Build chatML format 
#Train
#Validate
#merge adapters
#download llama.cpp and check if llama.quantise llama.imatrix, convert_to_gguf exists
#bash gguf_convert.sh
#python calibration.py
#bash quantize (if fails to find imatrix cp llama.cpp/build/bin/llama-* llama.cpp/)


# (ai_interview_platform)$ wc -c llama.cpp/calibration_data.txt
# 2521171 llama.cpp/calibration_data.txt
# (ai_interview_platform)$ head -c 250000 llama.cpp/calibration_data.txt > llama.cpp/calibration_data_small.txt
# (ai_interview_platform)$ bash quantize.sh finetune/gguf/model-f16.gguf llama.cpp/calibration_data_small.txt
# bash: quantize.sh: No such file or directory

# The imatrix's job is to estimate, per weight, "how much does this weight matter for typical outputs" by observing activations on a sample of representative text. Once you have a few hundred KB to a couple MB of reasonably representative text, more data gives rapidly diminishing returns — you're not meaningfully improving quantization quality by running all 815 examples through it instead of 100-150,
# ./llama.cpp/llama-cli -m finetune/gguf/model-Q4_K_M.gguf -p "Hello!"

#ollama create mockai-tutor -f Modelfile

# ls llama.cpp/llama-imatrix llama.cpp/llama-quantize
# bash quantize.sh finetune/gguf/model-f16.gguf llama.cpp/calibration_data_small.txt
# ls llama.cpp/llama-imatrix 2>&1
# ls llama.cpp/build/bin/llama-imatrix 2>&1





#runs where llama.cpp exists
# (ai_interview_platform)$ bash finetune/scripts/gguf_convert.sh finetune/merged/mer
# ged_model_with_eos finetune/gguf/model-retrain-f16.gguf
#Mistake that i did because of which i had to retrain thrice was the issue first time after training it gave in russian, second mistake is it didnt learn to stop and third worked. I didnt follow documentation or youtube jumped into coding i think it was good and bad, bad because we need to learn certain way of using built-in libraries but good because I it helped me to understand through break and learn which helped me to learn 100 other concepts of finetuning and llm. SO THE STATEMENT BREAK AND LEARN WAS USEFUL TO ME


# FROM ./model-Q4_K_M.gguf
# TEMPLATE """{{ if .System }}<|im_start|>system
# {{ .System }}<|im_end|>
# {{ end }}{{ if .Prompt }}<|im_start|>user
# {{ .Prompt }}<|im_end|>
# {{ end }}<|im_start|>assistant
# {{ .Response }}<|im_end|>
# """
# PARAMETER stop "<|im_end|>"
# PARAMETER num_ctx 2048


# FROM ./model-retrain-Q4_K_M.gguf
# TEMPLATE """{{ if .System }}<|im_start|>system
# {{ .System }}<|im_end|>
# {{ end }}{{ if .Prompt }}<|im_start|>user
# {{ .Prompt }}<|im_end|>
# {{ end }}<|im_start|>assistant
# """

# PARAMETER stop "<|im_end|>"
# PARAMETER num_ctx 2048
# EOF
# ollama create mockai-tutor-new -f Modelfile
