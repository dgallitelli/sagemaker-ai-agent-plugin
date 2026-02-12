#!/usr/bin/env python3
"""
Fine-tune an LLM with QLoRA (4-bit quantization + LoRA) using SFTTrainer.

This script is designed to run inside a SageMaker Training Job container.
It receives hyperparameters via environment variables and reads training data
from the SageMaker input channel.

4-bit quantized training - most memory efficient option.
Can fine-tune 7-8B models on single 24GB GPU, or 70B on 4x A10G.

Dataset format (JSONL):
    {"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
"""
import os
import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer, SFTConfig


def main():
    # ==========================================================================
    # Configuration from environment variables (passed via hyperparameters)
    # ==========================================================================
    model_id = os.environ.get("MODEL_ID", "meta-llama/Llama-3.1-8B-Instruct")
    train_data = os.environ.get("SM_CHANNEL_TRAIN", "/opt/ml/input/data/train")
    output_dir = os.environ.get("SM_MODEL_DIR", "/opt/ml/model")

    # Training hyperparameters
    num_epochs = int(os.environ.get("NUM_EPOCHS", "3"))
    batch_size = int(os.environ.get("BATCH_SIZE", "2"))
    gradient_accumulation = int(os.environ.get("GRADIENT_ACCUMULATION", "4"))
    learning_rate = float(os.environ.get("LEARNING_RATE", "2e-4"))
    max_seq_length = int(os.environ.get("MAX_SEQ_LENGTH", "2048"))

    # LoRA hyperparameters
    lora_r = int(os.environ.get("LORA_R", "16"))
    lora_alpha = int(os.environ.get("LORA_ALPHA", "32"))

    print("=" * 60)
    print("Training Configuration")
    print("=" * 60)
    print(f"Model:          {model_id}")
    print(f"Train data:     {train_data}")
    print(f"Output:         {output_dir}")
    print(f"Epochs:         {num_epochs}")
    print(f"Batch size:     {batch_size}")
    print(f"Grad accum:     {gradient_accumulation}")
    print(f"Effective batch:{batch_size * gradient_accumulation}")
    print(f"Learning rate:  {learning_rate}")
    print(f"Max seq length: {max_seq_length}")
    print(f"LoRA r:         {lora_r}")
    print(f"LoRA alpha:     {lora_alpha}")
    print("=" * 60)

    # ==========================================================================
    # Load tokenizer
    # ==========================================================================
    print("\nLoading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # ==========================================================================
    # Configure 4-bit quantization (QLoRA)
    # ==========================================================================
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",            # NormalFloat4 quantization
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,       # Nested quantization for memory savings
    )

    # ==========================================================================
    # Load model with quantization
    # ==========================================================================
    print("Loading model with 4-bit quantization...")
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
    )
    model.config.use_cache = False  # Required for gradient checkpointing

    # Prepare model for k-bit training
    model = prepare_model_for_kbit_training(model)

    # ==========================================================================
    # Configure LoRA
    # ==========================================================================
    peft_config = LoraConfig(
        r=lora_r,
        lora_alpha=lora_alpha,
        lora_dropout=0.05,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",  # Attention layers
            "gate_proj", "up_proj", "down_proj"       # MLP layers
        ],
        bias="none",
        task_type="CAUSAL_LM",
    )

    # Apply LoRA adapters
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    # ==========================================================================
    # Load dataset
    # ==========================================================================
    print(f"\nLoading dataset from {train_data}...")
    dataset = load_dataset("json", data_files={
        "train": f"{train_data}/train.jsonl",
    })

    # Check if validation split exists
    val_path = f"{train_data}/val.jsonl"
    if os.path.exists(val_path):
        val_dataset = load_dataset("json", data_files={"validation": val_path})
        dataset["validation"] = val_dataset["validation"]
        print(f"Validation samples: {len(dataset['validation'])}")

    print(f"Training samples: {len(dataset['train'])}")

    # ==========================================================================
    # Data formatting function
    # ==========================================================================
    # Expects data in chat format: {"messages": [{"role": "user", "content": "..."}, ...]}
    def formatting_func(example):
        messages = example.get("messages", [])
        if not messages:
            return ""
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False
        )

    # ==========================================================================
    # Training configuration
    # ==========================================================================
    sft_config = SFTConfig(
        output_dir=output_dir,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=gradient_accumulation,
        learning_rate=learning_rate,
        lr_scheduler_type="cosine",
        warmup_ratio=0.1,
        max_seq_length=max_seq_length,
        bf16=True,
        logging_steps=10,
        save_strategy="epoch",
        save_total_limit=2,
        optim="paged_adamw_8bit",
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        report_to="none",
        packing=False,
        dataset_text_field=None,
    )

    # ==========================================================================
    # Create trainer and train
    # ==========================================================================
    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=dataset["train"],
        eval_dataset=dataset.get("validation"),
        tokenizer=tokenizer,
        formatting_func=formatting_func,
        peft_config=peft_config,
    )

    print("\nStarting training...")
    trainer.train()

    # ==========================================================================
    # Save model
    # ==========================================================================
    print(f"\nSaving model to {output_dir}...")
    trainer.save_model()
    tokenizer.save_pretrained(output_dir)

    print("\nTraining completed!")


if __name__ == "__main__":
    main()
