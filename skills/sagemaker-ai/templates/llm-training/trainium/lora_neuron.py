#!/usr/bin/env python3
"""LoRA Fine-tuning for AWS Trainium using Neuron SDK.

This script is designed to run inside a SageMaker Training Job container
on Trainium (trn1) instances. It receives hyperparameters via environment
variables and reads training data from the SageMaker input channel.

Trainium-specific adaptations:
- Uses eager attention (no flash_attention_2)
- No device_map="auto"
- Compatible with Neuron compiler

Dataset format (JSONL):
    {"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
"""
import os

import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model
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
    batch_size = int(os.environ.get("BATCH_SIZE", "1"))
    gradient_accumulation = int(os.environ.get("GRADIENT_ACCUMULATION", "8"))
    learning_rate = float(os.environ.get("LEARNING_RATE", "1e-4"))
    max_seq_length = int(os.environ.get("MAX_SEQ_LENGTH", "4096"))

    # LoRA hyperparameters
    lora_r = int(os.environ.get("LORA_R", "16"))
    lora_alpha = int(os.environ.get("LORA_ALPHA", "32"))

    # Whether to merge LoRA weights at the end
    merge_and_save = os.environ.get("MERGE_AND_SAVE", "false").lower() == "true"

    print("=" * 60)
    print("Trainium LoRA Training Configuration")
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
    print(f"Merge weights:  {merge_and_save}")
    print("=" * 60)
    print("NOTE: Using Trainium-optimized settings (eager attention, no device_map)")
    print("=" * 60)

    # ==========================================================================
    # Load tokenizer
    # ==========================================================================
    print("\nLoading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # ==========================================================================
    # Load model with Trainium-compatible settings
    # NOTE: No flash_attention_2, no device_map="auto"
    # ==========================================================================
    print("Loading model in bf16 (Trainium-compatible)...")
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
        attn_implementation="eager",  # Trainium compatible - no flash_attention_2
        # NOTE: Do NOT use device_map="auto" on Trainium
    )
    model.config.use_cache = False  # Required for gradient checkpointing

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
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        report_to="none",
        packing=False,
        dataset_text_field=None,
        ddp_find_unused_parameters=False,  # Required for Trainium
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

    print("\nStarting LoRA training on Trainium...")
    trainer.train()

    # ==========================================================================
    # Save model
    # ==========================================================================
    print(f"\nSaving model to {output_dir}...")
    if merge_and_save:
        print("Merging LoRA weights into base model...")
        merged_model = trainer.model.merge_and_unload()
        merged_model.save_pretrained(output_dir)
    else:
        trainer.save_model()

    tokenizer.save_pretrained(output_dir)

    print("\nTrainium LoRA training completed!")


if __name__ == "__main__":
    main()
