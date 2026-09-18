# Recipe Sources and Search Queries

## Primary Recipe Repository (Recommended)

**aws-samples/amazon-sagemaker-generativeai** - Model Customization Recipes
- Branch: `feature/gpro-rlvr-recipes`
- Path: `0_model_customization_recipes/`
- URL: https://github.com/aws-samples/amazon-sagemaker-generativeai/tree/feature/gpro-rlvr-recipes/0_model_customization_recipes

### Available Recipes by Model Family

| Model Family | Models | Training Methods |
|--------------|--------|------------------|
| **Meta Llama** | Llama-3.2-3B, Llama-3.3-70B, Llama-3.2-11B-Vision, Llama-4-Maverick-17B | LoRA, Spectrum, Full FT |
| **Qwen** | Qwen2.5-3B, QwQ-32B, Qwen2-Audio-7B, Qwen3-VL-2B/4B | LoRA, Spectrum, Full FT |
| **DeepSeek** | DeepSeek-R1-0528, DeepSeek-R1-Distill-Qwen-1.5B | LoRA, Spectrum, Full FT |
| **Microsoft** | Phi-3-mini-128k, Phi-4 | LoRA, Spectrum, Full FT |
| **Google** | Gemma-3-4B, Gemma-3-27B | LoRA, Spectrum, Full FT |
| **OpenAI-style** | GPT-OSS-20B, GPT-OSS-120B | LoRA, Spectrum, Full FT |

### Training Methods Explained

1. **LoRA/QLoRA**: Parameter-efficient, low memory, runs on smaller GPUs. Best for rapid iteration.
2. **Spectrum Training**: Selective parameter fine-tuning targeting specific layers. Balanced performance.
3. **Full Fine-Tuning**: Complete model adaptation. Maximum specialization, highest resource needs.

## Secondary Recipe Repository

**aws/sagemaker-hyperpod-recipes** - HyperPod-optimized recipes
- URL: https://github.com/aws/sagemaker-hyperpod-recipes
- Focus: Large-scale distributed training on HyperPod clusters
- Includes: SFT, DPO, RLHF, RLVR recipes

## How to Find the Right Recipe

1. **Match model family**: Find recipe folder matching your base model (e.g., `llama/`, `qwen/`)
2. **Match training method**: Select subfolder for technique (LoRA, Spectrum, Full)
3. **Check modality**: Vision/audio models have specialized recipes
4. **Verify instance compatibility**: Recipe includes recommended instance types

## Fetching Latest Recipes

To clone and explore recipes:

```bash
# Clone the repository
git clone https://github.com/aws-samples/amazon-sagemaker-generativeai.git
cd amazon-sagemaker-generativeai
git checkout feature/gpro-rlvr-recipes

# Browse recipes
ls 0_model_customization_recipes/
```

## Recipe Structure

Each recipe typically includes:
- `*.ipynb` - Jupyter notebook for SageMaker Studio
- `config.yaml` - Training configuration
- `requirements.txt` - Python dependencies
- `train.py` - Training entrypoint script

## Customizing Recipes for Your Use Case

When adapting a recipe:
1. **Change model_id**: Point to your base model
2. **Update data paths**: Your S3 dataset location
3. **Adjust hyperparameters**: Learning rate, batch size, epochs
4. **Select instance type**: Based on model size and technique
5. **Configure output**: S3 location for checkpoints and final model
