# Best Practices & Advisory

## Default Recommendation: Start with PeFT

**Always recommend LoRA/QLoRA first** unless the user explicitly requests otherwise.

Rationale:
- Fastest iteration cycle
- Lowest resource cost
- Sufficient for most use cases
- Easy to experiment with multiple configurations

Only escalate to Spectrum or Full fine-tuning when:
- User has specific quality requirements that PeFT can't meet
- Domain shift is significant (biomedical, legal, scientific)
- User explicitly requests maximum specialization

## Technique Selection Guide

### When to Recommend LoRA/QLoRA
- Rapid prototyping and experimentation
- Memory-constrained environments
- Instruction-following tasks
- Lightweight domain adaptation
- Running multiple experiments on same base model

### When to Recommend Spectrum Training
- LoRA underperforms on the task
- Moderate domain shift
- Need more capacity than LoRA but not full fine-tuning cost
- Ablation studies on which layers matter most

### When to Recommend Full Fine-Tuning
- Heavy domain shift (biomedical, legal, financial)
- Complex reasoning requiring maximum accuracy
- User has ample compute budget
- Deep behavioral transformation needed

## Hyperparameter Recommendations

### Learning Rate
- **Range**: 5e-5 to 2e-4
- **Schedule**: Cosine with warmup (10% warmup ratio)
- **LoRA**: Use higher end (~1e-4 to 2e-4)
- **Full FT**: Use lower end (~1e-5 to 5e-5)

### LoRA Configuration
- **Rank (r)**: Start with 16; try 32-64 for complex tasks
- **Alpha**: Typically 2× rank (e.g., r=16, alpha=32)
- **Target modules**: All linear layers for comprehensive coverage:
  ```
  q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj
  ```

### Batch Size
- Start with `per_device_train_batch_size=1`
- Use `gradient_accumulation_steps` to achieve effective batch size of 8-32
- Larger effective batch = more stable training

### Sequence Length
- Default: 4096 tokens
- Increase for long-context tasks
- Enable packing for short sequences to maximize GPU utilization

## Memory Optimization (OOM Recovery)

When facing Out of Memory errors, apply in this order:

1. **Reduce batch size** incrementally
2. **Enable gradient checkpointing** (trades compute for memory)
3. **Enable 4-bit quantization** (QLoRA with bitsandbytes)
4. **Reduce max_seq_length** if task permits
5. **Move to larger instance** as last resort

## Built-in Optimizations

The AWS sample recipes include automatic optimizations:
- Flash Attention 2/3 (FA3 on H100+)
- Liger Kernel for efficient training
- Gradient checkpointing
- 4-bit quantization support

## Common Pitfalls to Warn Users About

### Data Format
- Must use conversational format: `{"messages": [{"role": "...", "content": "..."}]}`
- Validate JSONL structure before training
- Empty completions cause poor results

### Configuration
- Verify YAML indentation
- Check S3 paths are correct
- Ensure IAM role has necessary permissions

### Multimodal Models
- Need 2× memory vs text-only equivalent
- Verify processor configuration matches model
- Don't truncate image tokens

### Full Fine-Tuning
- Needs 2-4× more memory than PeFT
- Test on small data first
- Plan for longer training times

## Cost Optimization Tips

### Use Spot Instances
- 50-70% cost savings
- Good for fault-tolerant workloads
- Enable checkpointing for recovery

### Enable Warm Pools
```python
keep_alive_period_in_seconds=1800  # 30 minutes
```
Avoids repeated startup overhead for iterative training.

### Right-Size Instances
- Don't over-provision
- Use decision tree to match model size to instance
- Test on smaller scale before production

## Experiment Tracking

Recommend enabling logging from the start:
- MLflow for comprehensive tracking
- TensorBoard for visualization
- CloudWatch for monitoring

## Advisory Summary

When starting a new training project:

1. **Start with LoRA** on smallest recommended instance
2. **Validate data format** before launching
3. **Enable checkpointing** for fault tolerance
4. **Use Spot instances** for cost savings
5. **Compare techniques** on representative data before production
6. **Monitor GPU utilization** - should be high (>80%)
7. **Scale up gradually** based on results
