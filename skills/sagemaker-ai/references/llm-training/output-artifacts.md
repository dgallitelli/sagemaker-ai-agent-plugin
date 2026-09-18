# Output Artifacts

Generate appropriate artifacts based on user's output preference.

## Ask User: Notebook or Script?

Use `AskUserQuestion` with options:
- **Jupyter Notebook** - For SageMaker Studio, interactive development
- **Python Script** - Standalone CLI launcher, CI/CD friendly

## Option A: Python Script Launcher

### File Structure
```
training_project/
├── launch_training.py      # Main launcher script
├── train.py                # Training entrypoint (or user's script)
├── requirements.txt        # Dependencies
├── config/
│   └── training_config.yaml # Hyperparameters
└── README.md               # Quick start instructions
```

### Launch Script Template
Use `templates/llm-training/launch_training_job.py` as base, customize:
- Model ID
- Instance type and count
- S3 paths (dataset, output)
- Hyperparameters
- Container image

### Training Entrypoint
Based on technique, use appropriate template:
- `templates/llm-training/sft_trl.py` - Full SFT
- `templates/llm-training/lora_peft.py` - LoRA
- `templates/llm-training/qlora_peft.py` - QLoRA
- `templates/llm-training/dpo_trl.py` - DPO
- `templates/llm-training/cpt_hf.py` - Continued pretraining

### Run Instructions
```bash
# From local machine
python launch_training.py \
    --role-arn arn:aws:iam::ACCOUNT:role/SageMakerExecutionRole \
    --s3-train s3://bucket/data/train/ \
    --s3-output s3://bucket/outputs/ \
    --instance-type ml.g5.12xlarge

# Or with config file
python launch_training.py --config config/training_config.yaml
```

## Option B: Jupyter Notebook

### Structure
Single notebook with sections:
1. **Setup** - Install dependencies, configure
2. **Data** - Load and preview dataset
3. **Estimator** - Configure SageMaker estimator
4. **Training** - Launch and monitor
5. **Results** - Download and evaluate

### Notebook Template Pattern
```python
# Cell 1: Setup
!pip install -q sagemaker transformers peft trl

import sagemaker
from sagemaker.pytorch import PyTorch

role = sagemaker.get_execution_role()
sess = sagemaker.Session()

# Cell 2: Configuration
config = {
    "model_id": "meta-llama/Llama-3.1-8B-Instruct",
    "technique": "lora",
    "max_seq_length": 4096,
    "learning_rate": 1e-4,
    # ... more hyperparameters
}

# Cell 3: Define Estimator
estimator = PyTorch(
    entry_point="train.py",
    source_dir="./src",
    role=role,
    instance_type="ml.g5.12xlarge",
    instance_count=1,
    framework_version="2.5.1",
    py_version="py311",
    hyperparameters=config,
)

# Cell 4: Launch Training
estimator.fit({
    "train": "s3://bucket/data/train/"
})

# Cell 5: Results
# Download model, run evaluation
```

## Option C: HyperPod Artifacts

### File Structure
```
hyperpod_training/
├── recipe_config.yaml      # Training configuration
├── submit_slurm.sh         # Slurm submission script
├── train.py                # Training entrypoint
└── README.md               # Setup and usage
```

### Use Templates
- `templates/llm-training/hyperpod/recipe_config.yaml`
- `templates/llm-training/hyperpod/submit_slurm.sh`

### Run Instructions
```bash
# SSH to HyperPod head node
ssh hyperpod-cluster

# Submit job
sbatch submit_slurm.sh recipe_config.yaml

# Monitor
squeue -u $USER
tail -f logs/llm-training_*.out
```

## Output Checklist

Before delivering, verify:

- [ ] All S3 paths are parameterized (user must fill in)
- [ ] IAM role ARN is parameterized
- [ ] Instance type matches recommendations
- [ ] Container image is correct for accelerator
- [ ] Requirements.txt includes all dependencies
- [ ] Training script arguments match estimator hyperparameters
- [ ] Output includes clear run instructions

## Customization Points

Highlight these for user to customize:
1. **Model ID** - Their base model
2. **S3 paths** - Dataset and output locations
3. **Instance type** - Per sizing recommendations
4. **Hyperparameters** - LR, batch size, epochs
5. **LoRA config** - Rank, alpha, target modules (if applicable)
