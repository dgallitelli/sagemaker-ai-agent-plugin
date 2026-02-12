---
name: sagemaker-llm-training-skill
description: >
  Standard Operating Procedure (SOP) for training and fine-tuning LLMs on Amazon SageMaker.
  Use when the user wants to: fine-tune, continued pretraining, CPT, preference optimization,
  DPO, RLHF, LoRA, QLoRA, Spectrum, full fine-tuning, SFT on SageMaker. Also use when choosing
  between SageMaker Training Jobs vs HyperPod clusters, selecting training containers (DLC),
  or GPU vs Trainium instances. Generates runnable notebooks or Python scripts.
  Triggers: "train llm", "fine-tune", "sagemaker training", "lora training", "qlora",
  "hyperpod training", "trainium training", "dlc container", "training job".
argument-hint: "[model-id or 'start']"
---

# SageMaker LLM Training Operator (SOP)

Guide users from intent → **executable SageMaker training launcher** using official AWS recipes when possible.

## Guardrails

- **Scope**: AWS SageMaker Training only (Training Jobs or HyperPod)
- **Produce artifacts**: Deliver runnable code, not just advice
- **Dynamic info**: Fetch current container images and instance availability - do not hardcode versions
- **Python version**: SageMaker SDK v3 requires Python ≤3.13 (incompatible with 3.14+)
- **DLC images source**: https://aws.github.io/deep-learning-containers/reference/available_images/ (authoritative)
- **Neuron compatibility**: https://huggingface.co/docs/optimum-neuron/en/supported_architectures (authoritative)
- **Primary recipe source**: https://github.com/aws-samples/amazon-sagemaker-generativeai/tree/feature/gpro-rlvr-recipes/0_model_customization_recipes

## Wizard Mode (CRITICAL)

**Ask ONE question at a time. Wait for response before proceeding.**

Use `AskUserQuestion` for choices. Use plain text for open-ended questions.

---

## Wizard Steps

### Step 1: Model
Ask: "Which model do you want to train?"
- Examples: `meta-llama/Llama-3.1-8B-Instruct`, `Qwen/Qwen2.5-7B-Instruct`
- Accept: HuggingFace ID or S3 path

→ Wait for response.

---

### Step 2: Region
Ask: "Which AWS region should we use for training?"
- Suggest: `us-east-1`, `us-west-2` (best GPU/Trainium availability)
- If user says "default" or doesn't specify, use `us-east-1`

→ Wait for response.

---

### Step 3: Training Objective
Use `AskUserQuestion`:
- **Instruction SFT** - Fine-tune on instruction-response pairs
- **Continued Pretraining (CPT)** - Extend training on domain corpus
- **Preference Optimization (DPO)** - Align with human preferences

→ Wait for response.

---

### Step 4: Code Readiness
Use `AskUserQuestion`:
- **No, I need a recipe** - Use AWS sample recipes (recommended)
- **Yes, I have my own code** - Bring existing training script

→ If **No**: Go to Step 5A (Recipe path)
→ If **Yes**: Go to Step 5B (Custom code path)

---

### Step 5A: Recipe Selection (No existing code)

**IMPORTANT**: Check what recipes actually exist before offering technique choices.

1. **Fetch available recipes** from the primary recipe repo:
   ```
   https://github.com/aws-samples/amazon-sagemaker-generativeai/tree/feature/gpro-rlvr-recipes/0_model_customization_recipes
   ```

2. **Match model family** to available recipes:
   - Look for folder matching model family (llama, qwen, gemma, phi, deepseek, etc.)
   - Note which techniques are available (QLoRA, Spectrum, Full)

3. **Present ONLY available techniques** using `AskUserQuestion`:
   - Only show techniques that exist in the repo for this model family
   - Example: Gemma has QLoRA and Full, but NOT Spectrum or LoRA

| Model Family | Available Techniques |
|--------------|---------------------|
| Llama | QLoRA, Spectrum, Full |
| Qwen | QLoRA, Spectrum, Full |
| Gemma | QLoRA, Full |
| Phi | QLoRA, Spectrum, Full |
| DeepSeek | QLoRA, Spectrum, Full |

→ Continue to Step 6.

---

### Step 5B: Custom Code Path (Has existing code)

1. Ask: "Path to your training script and requirements.txt?"
2. Inspect requirements: `python scripts/inspect_requirements.py <path>`
3. Determine accelerator from dependencies per [references/container-selection.md](references/container-selection.md)

→ Continue to Step 6.

---

### Step 6: Infrastructure
Use `AskUserQuestion`:
- **SageMaker Training Jobs** - Transient, pay-per-use, simpler setup
- **SageMaker HyperPod** - Persistent cluster, Slurm/EKS orchestration

→ Wait for response.

---

### Step 7: Accelerator

**IMPORTANT**: Check Neuron compatibility BEFORE offering Trainium.

1. **Verify model support** using WebFetch:
   ```
   WebFetch: https://huggingface.co/docs/optimum-neuron/en/supported_architectures
   Prompt: "Is <model_type> supported for training on Trainium/Neuron?"
   ```

2. **Decision tree**:
   - If architecture **explicitly listed** → Offer both GPU and Trainium
   - If architecture **not listed** but user wants Trainium → Offer compilation test
   - If architecture **not listed** and user doesn't need Trainium → Use GPU

3. **Present appropriate options** using `AskUserQuestion`:

   **If architecture is supported:**
   - **GPU (NVIDIA)** - Broad model support, QLoRA compatible
   - **Trainium** - Cost-effective for supported models (no 4-bit)

   **If architecture is NOT in supported list:**
   - **GPU (NVIDIA)** - Guaranteed compatibility (Recommended)
   - **Test Trainium compatibility** - Launch EC2 instance to verify (~$0.30)

4. **If user chooses "Test Trainium compatibility"**:

   Follow [references/neuron-compile-test.md](references/neuron-compile-test.md):

   a. **Ask about SSH key** using `AskUserQuestion`:
      - **Use existing key pair** - I have an EC2 key pair
      - **Create new key pair** - Create one for me

   b. **If creating new key**, run:
      ```bash
      aws ec2 create-key-pair --key-name neuron-compile-test-key \
        --query 'KeyMaterial' --region <region> --output text > neuron-compile-test-key.pem
      chmod 400 neuron-compile-test-key.pem
      ```

   c. **Deploy test instance** (requires user approval):
      ```bash
      aws cloudformation create-stack --stack-name neuron-compile-test \
        --template-body file://templates/trainium/cfn-neuron-compile-test.yaml \
        --parameters ParameterKey=KeyPairName,ParameterValue=<key-name> \
        --region <region>
      ```

   d. **Run test (one-liner)**:
      ```bash
      IP=$(aws cloudformation describe-stacks --stack-name neuron-compile-test \
        --query 'Stacks[0].Outputs[?OutputKey==`PublicIP`].OutputValue' --output text --region <region>)
      ssh -i <key>.pem ubuntu@$IP "source /opt/aws_neuronx_venv_pytorch_2_5_nxd_training/bin/activate && \
        pip install -q 'transformers>=5.0' && cd ~/neuron-test && \
        MODEL_ID='<model-id>' python test_neuron_compile.py"
      ```

   e. **Expected output** - Look for the copyable summary block at the end:
      ```
      ############################################################
      # COPY THIS SUMMARY:
      ############################################################
      Model: <model-id>
      Status: PASSED
      Architecture: <model_type>
      Parameters: <X.XX>B
      Memory Warning: YES (if present, needs larger instance)
      ############################################################
      ```
      Full log saved to: `~/neuron-test/last_test.log`

   f. **Ask user to confirm result** using `AskUserQuestion`:
      - **Compilation PASSED** - I see "Compiler status PASS" in the output
      - **PASSED with memory warnings** - Passed but saw "Failed to allocate" errors
      - **Compilation FAILED** - I see errors or "Compiler status FAIL"
      - **Need help interpreting** - Not sure what the output means

      → If **PASSED** (no warnings): Proceed with Trainium, go to cleanup
      → If **PASSED with memory warnings**: Model is compatible but needs larger instance:
        - trn1.2xlarge (32GB) too small → recommend trn1.32xlarge (512GB)
        - Note: Training needs 3-4x more memory than inference (gradients, optimizer)
        - Proceed with Trainium but select larger instance in Step 10
      → If **FAILED**: Check error type:
        - `int64 matmul not supported` → Use GPU instead (incompatible)
        - `model_type not recognized` → Check transformers version
        - Other errors → See [references/neuron-compile-test.md](references/neuron-compile-test.md)
      → If **Need help**: Ask user to paste output, help interpret

   g. **Cleanup**:
      ```bash
      aws cloudformation delete-stack --stack-name neuron-compile-test --region <region>
      ```

→ If Trainium + QLoRA selected: Error - QLoRA not supported on Trainium
→ Wait for response.

---

### Step 8: Dataset
Ask: "Where is your training dataset?"
- Accept: HuggingFace Hub dataset name (e.g., `databricks/dolly-15k`)
- Accept: S3 URI with JSONL/Parquet files
- Validate format per [references/data-contract.md](references/data-contract.md)

→ Wait for response.

---

### Step 9: Context Length
Use `AskUserQuestion`:
- **4k tokens** - Standard, lower memory
- **8k tokens** - Balanced
- **16k+ tokens** - Long context (higher memory)

→ Wait for response.

---

### Step 10: Instance Sizing

Based on collected info, recommend instances per [references/instance-sizing.md](references/instance-sizing.md).

1. **Get recommendations**:
   ```bash
   python scripts/fetch_instance_info.py --model-size <B> --technique <tech> --accelerator <gpu|trainium>
   ```

2. **Check quota availability** for recommended instances:
   ```bash
   aws service-quotas list-service-quotas --service-code sagemaker --region <region> \
     --query "Quotas[?contains(QuotaName, 'training') && contains(QuotaName, '<instance-type>')].{Name:QuotaName, Value:Value}"
   ```

3. **Present recommendations with quota status**:
   - Show primary and alternative instances
   - Indicate which have quota > 0
   - If primary has no quota, suggest requesting increase or using alternative

4. **If no quota in selected region**, check other regions:
   ```bash
   for region in us-west-2 eu-west-1; do
     aws service-quotas list-service-quotas --service-code sagemaker --region $region ...
   done
   ```

→ Wait for response.

---

### Step 11: Spot Instances (Cost Optimization)
Use `AskUserQuestion`:
- **Yes, use Spot instances** - 50-70% cost savings, may be interrupted
- **No, use On-Demand** - Higher cost, guaranteed capacity

→ If Spot: Enable checkpointing for fault tolerance
→ Wait for response.

---

### Step 12: S3 Output Bucket
Ask: "Where should we save the trained model? (S3 bucket or path)"

Options for discovery:
1. Ask user for S3 bucket/path
2. If user says "default": Use `sagemaker-{region}-{account_id}` bucket
3. Optionally discover existing SageMaker buckets:
   ```bash
   aws s3 ls | grep sagemaker
   ```
4. If multiple buckets found, confirm with user

→ Wait for response.

---

### Step 13: Execution Role
Ask: "Which IAM role should SageMaker use? (ARN or 'discover')"

Options for discovery:
1. Ask user for role ARN directly
2. If user says "discover" or "find": List SageMaker execution roles:
   ```bash
   aws iam list-roles --query "Roles[?contains(RoleName, 'SageMaker') || contains(RoleName, 'sagemaker')]"
   ```
3. If multiple roles found, present options and confirm
4. Verify role has required permissions (S3, ECR access)

→ Wait for response.

---

### Step 14: Output Format
Use `AskUserQuestion`:
- **Jupyter Notebook** - For SageMaker Studio
- **Python Script** - Standalone launcher, CI/CD friendly

→ Wait for response.

---

### Step 15: Generate Artifacts

1. **Fetch current container images** from the official AWS DLC page:
   ```
   WebFetch URL: https://aws.github.io/deep-learning-containers/reference/available_images/
   Prompt: "Find the latest PyTorch training <gpu|neuron> container image URI for SageMaker in <region>"
   ```

   Fallback (may have stale versions):
   ```bash
   python scripts/fetch_dlc_images.py --framework pytorch --region <region>
   ```

2. Select appropriate template from `templates/`:

   **GPU templates:**
   - `lora_peft.py` - LoRA with PEFT
   - `qlora_peft.py` - QLoRA (4-bit)
   - `sft_trl.py` - Full SFT
   - `dpo_trl.py` - DPO
   - `cpt_hf.py` - Continued pretraining

   **Trainium templates:**
   - `trainium/lora_neuron.py` - LoRA for Trainium (eager attention, no device_map)
   - `trainium/sft_neuron.py` - Full SFT for Trainium

   **Launcher:**
   - `launch_training_job.py` - SDK v3 ModelTrainer launcher

   **HyperPod:**
   - `hyperpod/` - HyperPod configs

3. Generate launcher using [references/output-artifacts.md](references/output-artifacts.md)

4. Run [references/checklist.md](references/checklist.md) before delivering

**Python Compatibility**: SageMaker SDK v3 requires Python ≤3.13 (incompatible with 3.14+)

---

## Reference Files

| File | Use When |
|------|----------|
| [references/best-practices.md](references/best-practices.md) | Default recommendations, technique selection, hyperparameters |
| [references/recipe-sources.md](references/recipe-sources.md) | Finding AWS sample recipes |
| [references/instance-sizing.md](references/instance-sizing.md) | Selecting instance types |
| [references/container-selection.md](references/container-selection.md) | Choosing container images |
| [references/neuron-validation.md](references/neuron-validation.md) | Verifying Trainium compatibility |
| [references/neuron-compile-test.md](references/neuron-compile-test.md) | Testing Neuron compilation for unknown models |
| [references/data-contract.md](references/data-contract.md) | Dataset format requirements |
| [references/output-artifacts.md](references/output-artifacts.md) | Generating final artifacts |
| [references/checklist.md](references/checklist.md) | Pre-delivery verification |

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/fetch_dlc_images.py` | Get current container images |
| `scripts/fetch_instance_info.py` | Get instance specs and recommendations |
| `scripts/inspect_requirements.py` | Analyze user's requirements.txt |
| `scripts/validate_dataset.py` | Validate dataset format |

## Templates

| Template | Training Method | Accelerator |
|----------|-----------------|-------------|
| `templates/lora_peft.py` | LoRA with PEFT | GPU |
| `templates/qlora_peft.py` | QLoRA (4-bit) | GPU |
| `templates/sft_trl.py` | Full SFT with TRL | GPU |
| `templates/dpo_trl.py` | DPO preference training | GPU |
| `templates/cpt_hf.py` | Continued pretraining | GPU |
| `templates/trainium/lora_neuron.py` | LoRA for Neuron SDK | Trainium |
| `templates/trainium/sft_neuron.py` | Full SFT for Neuron SDK | Trainium |
| `templates/trainium/cfn-neuron-compile-test.yaml` | Neuron compilation test EC2 | Trainium |
| `templates/launch_training_job.py` | SDK v3 ModelTrainer launcher | Both |
| `templates/hyperpod/` | HyperPod recipes | Both |

**Note**: Trainium templates use `attn_implementation="eager"` and no `device_map="auto"` for Neuron compatibility.
