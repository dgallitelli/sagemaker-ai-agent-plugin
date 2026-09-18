# Preflight Checklist

Run through this checklist before delivering final artifacts to user.

## Model Configuration

- [ ] **Model ID confirmed**: Verify HuggingFace ID or S3 path is correct
- [ ] **License checked**: User aware of model license requirements
- [ ] **Architecture supported**: For Trainium, verify Neuron compatibility

## Training Configuration

- [ ] **Objective confirmed**: SFT / CPT / DPO / other
- [ ] **Technique selected**: Full fine-tune / LoRA / QLoRA
- [ ] **LoRA config** (if applicable):
  - [ ] Rank (r) specified
  - [ ] Alpha specified
  - [ ] Target modules appropriate for model architecture

## Data Configuration

- [ ] **Dataset S3 URI provided**: User has confirmed location
- [ ] **Format validated**: JSONL/Parquet/HF Dataset
- [ ] **Schema matches**: Data columns match expected format
- [ ] **Train/validation split**: If validation data needed

## Infrastructure

- [ ] **Instance type recommended**: Based on model size + technique + context
- [ ] **Instance availability**: User aware to check regional availability
- [ ] **Accelerator type**: GPU vs Trainium confirmed
- [ ] **Distributed strategy**: FSDP/DeepSpeed if multi-GPU

## Container & Dependencies

- [ ] **Container image**: Correct DLC for accelerator type
- [ ] **Dependencies listed**: requirements.txt complete
- [ ] **Version compatibility**: PyTorch/Transformers/PEFT aligned

## Precision & Memory

- [ ] **Precision set**: BF16/FP16/4-bit as appropriate
- [ ] **Gradient checkpointing**: Enabled for long context or large models
- [ ] **Batch size + grad accum**: Effective batch size calculated

## Output Configuration

- [ ] **S3 output path**: User has provided destination
- [ ] **Checkpoint strategy**: save_strategy and save_steps configured
- [ ] **Final model location**: Clear where model will be saved

## Artifacts Delivered

- [ ] **Launch script OR notebook**: User preference honored
- [ ] **Training entrypoint**: Correct template for technique
- [ ] **Requirements.txt**: All dependencies included
- [ ] **Run instructions**: Clear command to execute

## Security & IAM

- [ ] **IAM role**: User knows they need SageMaker execution role
- [ ] **S3 permissions**: Role has access to data and output buckets
- [ ] **HuggingFace token**: If using gated models (Llama, etc.)

## Final Verification

- [ ] **No hardcoded secrets**: API keys, tokens parameterized
- [ ] **S3 paths parameterized**: User must fill in their paths
- [ ] **Instance type matches sizing**: Recommendation aligns with model/technique
- [ ] **Executable command provided**: User can run immediately

## Post-Launch Guidance

Remind user:
- Monitor CloudWatch logs for errors
- Check GPU utilization (should be high)
- First checkpoint confirms training started correctly
- Final model location in S3 output path
