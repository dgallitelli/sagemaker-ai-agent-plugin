"""QLoRA LLM fine-tuning script for SageMaker Training Jobs.

Usage: Set environment variables in ModelTrainer.environment, then launch via:
    SourceCode(source_dir="./scripts", command="pip install -r requirements.txt && python train_qlora.py")

Requirements (requirements.txt):
    torch
    transformers
    peft
    trl
    bitsandbytes
    datasets
    accelerate
"""

import os
import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, prepare_model_for_kbit_training
from trl import SFTTrainer, SFTConfig

# Config from environment variables (set in ModelTrainer.environment)
model_id = os.environ.get("MODEL_ID", "meta-llama/Llama-3.1-8B-Instruct")
train_data = os.environ.get("SM_CHANNEL_TRAIN", "/opt/ml/input/data/train")
output_dir = os.environ.get("SM_MODEL_DIR", "/opt/ml/model")
num_epochs = int(os.environ.get("NUM_EPOCHS", "3"))
batch_size = int(os.environ.get("BATCH_SIZE", "2"))
grad_accum = int(os.environ.get("GRADIENT_ACCUMULATION", "4"))
learning_rate = float(os.environ.get("LEARNING_RATE", "2e-4"))
max_seq_length = int(os.environ.get("MAX_SEQ_LENGTH", "2048"))
lora_r = int(os.environ.get("LORA_R", "16"))
lora_alpha = int(os.environ.get("LORA_ALPHA", "32"))

# 4-bit quantization config
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_use_double_quant=True,
)

# Load model
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    quantization_config=bnb_config,
    device_map="auto",
    torch_dtype=torch.bfloat16,
)
model = prepare_model_for_kbit_training(model)

# LoRA config
peft_config = LoraConfig(
    r=lora_r,
    lora_alpha=lora_alpha,
    lora_dropout=0.05,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                     "gate_proj", "up_proj", "down_proj"],
    bias="none",
    task_type="CAUSAL_LM",
)

# Load dataset — expects {"messages": [...]} format
dataset = load_dataset("json", data_files={"train": f"{train_data}/train.jsonl"})

# Tokenizer
tokenizer = AutoTokenizer.from_pretrained(model_id)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token


def formatting_func(example):
    return tokenizer.apply_chat_template(
        example["messages"], tokenize=False, add_generation_prompt=False
    )


# Training config
sft_config = SFTConfig(
    output_dir=output_dir,
    num_train_epochs=num_epochs,
    per_device_train_batch_size=batch_size,
    gradient_accumulation_steps=grad_accum,
    learning_rate=learning_rate,
    lr_scheduler_type="cosine",
    warmup_ratio=0.1,
    bf16=True,
    gradient_checkpointing=True,
    gradient_checkpointing_kwargs={"use_reentrant": False},
    logging_steps=10,
    save_strategy="epoch",
    save_total_limit=2,
    optim="paged_adamw_8bit",
    max_seq_length=max_seq_length,
)

# Train
trainer = SFTTrainer(
    model=model,
    args=sft_config,
    train_dataset=dataset["train"],
    processing_class=tokenizer,  # renamed from tokenizer in trl 0.12+
    formatting_func=formatting_func,
    peft_config=peft_config,
)
trainer.train()
trainer.save_model()
tokenizer.save_pretrained(output_dir)
print(f"Model saved to {output_dir}")
