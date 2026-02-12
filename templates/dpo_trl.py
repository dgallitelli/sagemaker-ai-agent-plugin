#!/usr/bin/env python3
"""Direct Preference Optimization (DPO) using TRL.

This script is designed to run inside a SageMaker Training Job container.
It receives hyperparameters via environment variables and reads training data
from the SageMaker input channel.

Aligns model with human preferences using chosen/rejected pairs.
Does not require a reward model like RLHF.

Requires: transformers, trl, datasets, accelerate, peft

Dataset format (JSONL):
    {"prompt": "...", "chosen": "...", "rejected": "..."}
    OR
    {"prompt": [{"role": "user", "content": "..."}],
     "chosen": [{"role": "assistant", "content": "..."}],
     "rejected": [{"role": "assistant", "content": "..."}]}
"""
import os

import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, TaskType
from trl import DPOTrainer, DPOConfig


def main():
    # ==========================================================================
    # Configuration from environment variables (passed via hyperparameters)
    # ==========================================================================
    model_id = os.environ.get("MODEL_ID", "meta-llama/Llama-3.1-8B-Instruct")
    train_data = os.environ.get("SM_CHANNEL_TRAIN", "/opt/ml/input/data/train")
    output_dir = os.environ.get("SM_MODEL_DIR", "/opt/ml/model")

    # Training hyperparameters
    num_epochs = int(os.environ.get("NUM_EPOCHS", "1"))
    batch_size = int(os.environ.get("BATCH_SIZE", "2"))
    gradient_accumulation = int(os.environ.get("GRADIENT_ACCUMULATION", "4"))
    learning_rate = float(os.environ.get("LEARNING_RATE", "5e-5"))
    max_length = int(os.environ.get("MAX_LENGTH", "1024"))
    max_prompt_length = int(os.environ.get("MAX_PROMPT_LENGTH", "512"))

    # DPO specific
    beta = float(os.environ.get("DPO_BETA", "0.1"))
    loss_type = os.environ.get("DPO_LOSS_TYPE", "sigmoid")

    # LoRA config (DPO typically uses LoRA for efficiency)
    use_lora = os.environ.get("USE_LORA", "true").lower() == "true"
    lora_r = int(os.environ.get("LORA_R", "16"))
    lora_alpha = int(os.environ.get("LORA_ALPHA", "32"))

    # Whether to merge LoRA weights at the end
    merge_and_save = os.environ.get("MERGE_AND_SAVE", "false").lower() == "true"

    print("=" * 60)
    print("DPO Training Configuration")
    print("=" * 60)
    print(f"Model:          {model_id}")
    print(f"Train data:     {train_data}")
    print(f"Output:         {output_dir}")
    print(f"Epochs:         {num_epochs}")
    print(f"Batch size:     {batch_size}")
    print(f"Grad accum:     {gradient_accumulation}")
    print(f"Effective batch:{batch_size * gradient_accumulation}")
    print(f"Learning rate:  {learning_rate}")
    print(f"Max length:     {max_length}")
    print(f"Max prompt len: {max_prompt_length}")
    print(f"DPO beta:       {beta}")
    print(f"DPO loss type:  {loss_type}")
    print(f"Use LoRA:       {use_lora}")
    if use_lora:
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
    # Load model (bf16)
    # ==========================================================================
    print("Loading model in bf16...")
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
        attn_implementation="flash_attention_2",
    )
    model.config.use_cache = False  # Required for gradient checkpointing

    # Reference model for DPO (frozen copy of base model)
    print("Loading reference model...")
    ref_model = AutoModelForCausalLM.from_pretrained(
        model_id,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
        attn_implementation="flash_attention_2",
    )

    # ==========================================================================
    # Configure LoRA (optional but recommended for DPO)
    # ==========================================================================
    peft_config = None
    if use_lora:
        peft_config = LoraConfig(
            r=lora_r,
            lora_alpha=lora_alpha,
            lora_dropout=0.05,
            target_modules=[
                "q_proj", "k_proj", "v_proj", "o_proj",  # Attention layers
                "gate_proj", "up_proj", "down_proj"       # MLP layers
            ],
            task_type=TaskType.CAUSAL_LM,
            bias="none",
        )
        print(f"Using LoRA: r={lora_r}, alpha={lora_alpha}")

    # ==========================================================================
    # Load dataset
    # ==========================================================================
    print(f"\nLoading dataset from {train_data}...")
    dataset = load_dataset("json", data_files={
        "train": f"{train_data}/train.jsonl",
    })

    # Validate DPO columns
    required_cols = {"prompt", "chosen", "rejected"}
    if not required_cols.issubset(set(dataset["train"].column_names)):
        raise ValueError(
            f"DPO dataset must have columns: {required_cols}. "
            f"Found: {dataset['train'].column_names}"
        )

    print(f"Training samples: {len(dataset['train'])}")

    # ==========================================================================
    # Training configuration
    # ==========================================================================
    training_args = DPOConfig(
        output_dir=output_dir,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=gradient_accumulation,
        learning_rate=learning_rate,
        lr_scheduler_type="cosine",
        warmup_ratio=0.1,
        weight_decay=0.01,
        beta=beta,
        loss_type=loss_type,
        max_length=max_length,
        max_prompt_length=max_prompt_length,
        bf16=True,
        logging_steps=10,
        save_strategy="epoch",
        save_total_limit=2,
        gradient_checkpointing=True,
        report_to="none",
    )

    # ==========================================================================
    # Create trainer and train
    # ==========================================================================
    trainer = DPOTrainer(
        model=model,
        ref_model=ref_model,
        args=training_args,
        train_dataset=dataset["train"],
        processing_class=tokenizer,
        peft_config=peft_config,
    )

    print(f"\nStarting DPO training (beta={beta}, loss={loss_type})...")
    trainer.train()

    # ==========================================================================
    # Save model
    # ==========================================================================
    print(f"\nSaving model to {output_dir}...")
    if merge_and_save and use_lora:
        print("Merging LoRA weights...")
        merged_model = trainer.model.merge_and_unload()
        merged_model.save_pretrained(output_dir)
    else:
        trainer.save_model(output_dir)

    tokenizer.save_pretrained(output_dir)

    print("\nDPO training completed!")


if __name__ == "__main__":
    main()
