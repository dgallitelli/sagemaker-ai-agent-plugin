# Dataset Schema Contract

Training scripts expect data in specific formats. Ensure user's data matches before training.

## Supported Formats

### 1. Conversational Format (Recommended for SFT)

```json
{"messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is the capital of France?"},
    {"role": "assistant", "content": "The capital of France is Paris."}
]}
```

- Supports multi-turn conversations
- System message is optional
- TRL's SFTTrainer auto-applies chat template

### 2. Prompt-Completion Format

```json
{"prompt": "What is the capital of France?", "completion": "The capital of France is Paris."}
```

- Simple instruction-response pairs
- Good for single-turn tasks

### 3. Text Format (for CPT)

```json
{"text": "Your domain-specific document text here..."}
```

- Raw text for continued pretraining
- Will be chunked into fixed-length sequences

### 4. Preference Format (for DPO)

```json
{
    "prompt": "What is the capital of France?",
    "chosen": "The capital of France is Paris.",
    "rejected": "France is a country in Europe."
}
```

Or conversational:
```json
{
    "prompt": [{"role": "user", "content": "What is the capital of France?"}],
    "chosen": [{"role": "assistant", "content": "The capital of France is Paris."}],
    "rejected": [{"role": "assistant", "content": "France is a country in Europe."}]
}
```

## File Formats

### JSONL (Recommended)
- One JSON object per line
- Easy to stream, append
- File extension: `.jsonl` or `.json`

### Parquet
- Columnar format, efficient for large datasets
- Better compression
- File extension: `.parquet`

### HuggingFace Dataset
- Pre-processed dataset saved with `dataset.save_to_disk()`
- Load with `load_from_disk()`

## Data Location

### S3 Structure
```
s3://your-bucket/datasets/
├── train/
│   ├── data_part_0.jsonl
│   ├── data_part_1.jsonl
│   └── ...
└── validation/  (optional)
    └── data.jsonl
```

### SageMaker Channel Mapping
```python
inputs = {
    "train": "s3://bucket/datasets/train/",
    "validation": "s3://bucket/datasets/validation/"  # optional
}
```

Data is mounted at:
- `/opt/ml/input/data/train/`
- `/opt/ml/input/data/validation/`

## Validation Script

Use to validate dataset before training:
```bash
python scripts/llm-training/validate_dataset.py s3://bucket/datasets/train/
```

Checks:
- File format and parsing
- Required columns present
- Message format validity
- Approximate token counts

## Common Issues

### Issue: Chat template not applied
- **Symptom**: Model outputs raw text without structure
- **Fix**: Use conversational format with `messages` column

### Issue: Truncation warnings
- **Symptom**: "Truncating sequence..." warnings during training
- **Fix**: Increase `max_seq_length` or filter long examples

### Issue: Empty responses
- **Symptom**: Model generates empty or very short responses
- **Fix**: Check that completion/assistant content is not empty

### Issue: Wrong format for DPO
- **Symptom**: DPO trainer errors about missing columns
- **Fix**: Ensure `prompt`, `chosen`, `rejected` columns exist
