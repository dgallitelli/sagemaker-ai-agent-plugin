#!/usr/bin/env python3
"""Continued Pretraining (CPT) using HuggingFace Trainer.

This script is designed to run inside a SageMaker Training Job container.
It receives hyperparameters via environment variables and reads training data
from the SageMaker input channel.

Extends model training on domain-specific corpus (raw text).
Used for domain adaptation before instruction tuning.

Requires: transformers, datasets, accelerate

Dataset format (JSONL):
    {"text": "Your domain-specific document text here..."}
"""
import os
from pathlib import Path

import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    DataCollatorForLanguageModeling,
)


def main():
    # ==========================================================================
    # Configuration from environment variables (passed via hyperparameters)
    # ==========================================================================
    model_id = os.environ.get("MODEL_ID", "meta-llama/Llama-3.1-8B-Instruct")
    train_data = os.environ.get("SM_CHANNEL_TRAIN", "/opt/ml/input/data/train")
    output_dir = os.environ.get("SM_MODEL_DIR", "/opt/ml/model")

    # Training hyperparameters
    num_epochs = int(os.environ.get("NUM_EPOCHS", "1"))
    batch_size = int(os.environ.get("BATCH_SIZE", "1"))
    gradient_accumulation = int(os.environ.get("GRADIENT_ACCUMULATION", "8"))
    learning_rate = float(os.environ.get("LEARNING_RATE", "1e-5"))  # Lower LR for CPT
    block_size = int(os.environ.get("BLOCK_SIZE", "2048"))
    text_column = os.environ.get("TEXT_COLUMN", "text")

    print("=" * 60)
    print("Continued Pretraining Configuration")
    print("=" * 60)
    print(f"Model:          {model_id}")
    print(f"Train data:     {train_data}")
    print(f"Output:         {output_dir}")
    print(f"Epochs:         {num_epochs}")
    print(f"Batch size:     {batch_size}")
    print(f"Grad accum:     {gradient_accumulation}")
    print(f"Effective batch:{batch_size * gradient_accumulation}")
    print(f"Learning rate:  {learning_rate}")
    print(f"Block size:     {block_size}")
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

    # ==========================================================================
    # Load dataset
    # ==========================================================================
    print(f"\nLoading dataset from {train_data}...")
    data_path = Path(train_data)
    if data_path.is_dir():
        jsonl_files = list(data_path.glob("*.jsonl")) + list(data_path.glob("*.json"))
        if jsonl_files:
            dataset = load_dataset("json", data_files=[str(f) for f in jsonl_files], split="train")
        else:
            txt_files = list(data_path.glob("*.txt"))
            if txt_files:
                dataset = load_dataset("text", data_files=[str(f) for f in txt_files], split="train")
            else:
                raise ValueError(f"No data files found in {train_data}")
    else:
        raise ValueError(f"Dataset path not found: {train_data}")

    print(f"Raw samples: {len(dataset)}")

    # ==========================================================================
    # Tokenize and chunk dataset
    # ==========================================================================
    def tokenize_function(examples):
        return tokenizer(examples[text_column], truncation=False)

    tokenized = dataset.map(
        tokenize_function,
        batched=True,
        remove_columns=dataset.column_names,
        desc="Tokenizing",
    )

    # Group texts into fixed-size chunks
    def group_texts(examples):
        concatenated = {k: sum(examples[k], []) for k in examples.keys()}
        total_length = len(concatenated["input_ids"])

        if total_length >= block_size:
            total_length = (total_length // block_size) * block_size

        result = {
            k: [t[i : i + block_size] for i in range(0, total_length, block_size)]
            for k, t in concatenated.items()
        }
        result["labels"] = result["input_ids"].copy()
        return result

    train_dataset = tokenized.map(group_texts, batched=True, desc="Chunking")
    print(f"Created {len(train_dataset)} chunks of {block_size} tokens")

    # ==========================================================================
    # Data collator
    # ==========================================================================
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False,  # Causal LM, not masked
    )

    # ==========================================================================
    # Training configuration
    # ==========================================================================
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=gradient_accumulation,
        learning_rate=learning_rate,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        weight_decay=0.01,
        bf16=True,
        logging_steps=10,
        save_strategy="steps",
        save_steps=500,
        save_total_limit=3,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        report_to="none",
        remove_unused_columns=False,
    )

    # ==========================================================================
    # Create trainer and train
    # ==========================================================================
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        data_collator=data_collator,
    )

    print("\nStarting continued pretraining...")
    trainer.train()

    # ==========================================================================
    # Save model
    # ==========================================================================
    print(f"\nSaving model to {output_dir}...")
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)

    print("\nContinued pretraining completed!")


if __name__ == "__main__":
    main()
