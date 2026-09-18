# Serverless Model Customization on SageMaker AI

## Overview

Serverless Model Customization is a fully managed capability in Amazon SageMaker AI that lets you fine-tune foundation models without provisioning or managing infrastructure. You select a model, choose a customization technique, point to your data, and SageMaker AI automatically provisions the appropriate compute resources (P5, P4de, P4d, G5) based on the model and data size.

Key characteristics:
- Completely serverless — no cluster setup, capacity planning, or distributed training expertise required
- Pay-per-token pricing
- Training and validation metrics logged to serverless MLflow
- Deploy to SageMaker AI inference endpoints or Amazon Bedrock
- Available in: us-east-1, us-west-2, eu-west-1, ap-northeast-1

## IMPORTANT: Supported Models Only

Serverless model customization supports a specific set of models. Not all models on SageMaker JumpStart or HuggingFace are eligible. If the user asks to customize a model not on this list, inform them it is not supported and suggest the closest alternative from the list, or recommend using SageMaker Training Jobs instead (see `training-jobs.md`).

As of March 2026, the following announcement expanded support to 12 additional open-weight models:
https://aws.amazon.com/about-aws/whats-new/2026/03/amazon-sagemaker-ai-serverless-additional-models/

### Full Supported Model List (March 2026)

The table below shows all supported models with their SDK model IDs. Models marked with ★ were added in the March 2026 expansion (12 additional models).

| Provider | Display Name | SDK Model ID | Added |
|----------|-------------|--------------|-------|
| Amazon Nova | Nova 2.0 Lite | `amazon-nova-2.0-lite` | ★ Mar 2026 |
| Amazon Nova | Nova Pro | `amazon-nova-pro` | Dec 2025 |
| Amazon Nova | Nova Lite | `amazon-nova-lite` | Dec 2025 |
| Amazon Nova | Nova Micro | `amazon-nova-micro` | Dec 2025 |
| Meta Llama | Llama 3.3 70B Instruct | `meta-llama/Llama-3.3-70B-Instruct` | ★ Mar 2026 |
| Meta Llama | Llama 3.1 8B Instruct | `meta-llama/Llama-3.1-8B-Instruct` | Dec 2025 |
| Meta Llama | Llama 3.2 3B Instruct | `meta-llama/Llama-3.2-3B-Instruct` | ★ Mar 2026 |
| Meta Llama | Llama 3.2 1B Instruct | `meta-llama/Llama-3.2-1B-Instruct` | Dec 2025 |
| Qwen | Qwen3-32B | `Qwen/Qwen3-32B` | ★ Mar 2026 |
| Qwen | Qwen3-14B | `Qwen/Qwen3-14B` | ★ Mar 2026 |
| Qwen | Qwen3-8B | `Qwen/Qwen3-8B` | ★ Mar 2026 |
| Qwen | Qwen3-4B | `Qwen/Qwen3-4B` | ★ Mar 2026 |
| Qwen | Qwen3-1.7B | `Qwen/Qwen3-1.7B` | ★ Mar 2026 |
| Qwen | Qwen3-0.6B | `Qwen/Qwen3-0.6B` | Dec 2025 |
| Qwen | Qwen2.5-72B-Instruct | `Qwen/Qwen2.5-72B-Instruct` | ★ Mar 2026 |
| Qwen | Qwen2.5-32B-Instruct | `Qwen/Qwen2.5-32B-Instruct` | Dec 2025 |
| Qwen | Qwen2.5-14B-Instruct | `Qwen/Qwen2.5-14B-Instruct` | ★ Mar 2026 |
| Qwen | Qwen2.5-7B-Instruct | `Qwen/Qwen2.5-7B-Instruct` | Dec 2025 |
| DeepSeek AI | DeepSeek-R1-Distill-Llama-70B | `deepseek-ai/DeepSeek-R1-Distill-Llama-70B` | ★ Mar 2026 |
| DeepSeek AI | DeepSeek-R1-Distill-Llama-8B | `deepseek-ai/DeepSeek-R1-Distill-Llama-8B` | ★ Mar 2026 |
| DeepSeek AI | DeepSeek-R1-Distill-Qwen-32B | `deepseek-ai/DeepSeek-R1-Distill-Qwen-32B` | Dec 2025 |
| DeepSeek AI | DeepSeek-R1-Distill-Qwen-14B | `deepseek-ai/DeepSeek-R1-Distill-Qwen-14B` | ★ Mar 2026 |
| DeepSeek AI | DeepSeek-R1-Distill-Qwen-7B | `deepseek-ai/DeepSeek-R1-Distill-Qwen-7B` | ★ Mar 2026 |
| DeepSeek AI | DeepSeek-R1-Distill-Qwen-1.5B | `deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B` | ★ Mar 2026 |
| OpenAI | gpt-oss-120b | `gpt-oss-120b` | ★ Mar 2026 |
| OpenAI | gpt-oss-20b | `gpt-oss-20b` | Dec 2025 |

Note: SDK model IDs are based on the HuggingFace Hub naming convention for open-weight models. Amazon Nova models use SageMaker-specific IDs. Always verify the exact model ID in SageMaker Studio's model catalog if you encounter errors.

This list may grow over time. Always check the SageMaker AI model customization page for the latest: https://aws.amazon.com/sagemaker/ai/model-customization/

### Technique-Model Compatibility

Not all models support all techniques. General guidance:
- SFT: Supported by all models
- DPO: Supported by all models
- RLVR: Supported by all models (requires a Lambda reward function)
- RLAIF: Supported by all models (requires a Bedrock judge model)

Check the SageMaker Studio UI for the definitive technique availability per model — the UI shows which techniques are available when you select a model.

## Supported Customization Techniques

| Technique | Description | Best For |
|-----------|-------------|----------|
| SFT (Supervised Fine-Tuning) | Train on curated prompt-completion pairs | High-quality labeled examples, straightforward adaptation |
| DPO (Direct Preference Optimization) | Train using preferred vs rejected response pairs | Aligning model behavior with human preferences |
| RLVR (Reinforcement Learning with Verifiable Rewards) | Model generates multiple candidates, reward function scores each, GRPO optimizes policy | Tasks with verifiable outcomes: tool calling, code gen, math, structured output |
| RLAIF (Reinforcement Learning from AI Feedback) | AI judge model evaluates responses instead of hand-written reward function | Subjective qualities: tone, helpfulness, instruction following |

### Technique Selection Guide

| Scenario | Recommended Technique |
|----------|----------------------|
| Domain-specific Q&A with labeled data | SFT |
| Chatbot tone/style alignment | DPO or RLAIF |
| Tool calling / function calling | RLVR |
| Code generation accuracy | RLVR (with code execution reward) |
| Math reasoning | RLVR (with math answer reward) |
| Safety and alignment | DPO or RLAIF |
| Instruction following improvement | RLAIF |
| No programmatic correctness metric available | RLAIF |

## Prerequisites

1. SageMaker AI domain with Studio access
2. AWS CLI configured with credentials
3. SageMaker Python SDK v3: `pip install 'sagemaker>=3'`
4. IAM execution role with required permissions (see below)
5. S3 bucket for datasets and outputs

### Required IAM Permissions

Attach these managed policies to your execution role:
- `AmazonSageMakerFullAccess`
- `AmazonSageMakerPipelinesIntegrations`
- `AmazonSageMakerModelRegistryFullAccess`

Plus this inline policy:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "LambdaPermissionsForRewardFunction",
            "Effect": "Allow",
            "Action": [
                "lambda:CreateFunction",
                "lambda:DeleteFunction",
                "lambda:InvokeFunction",
                "lambda:GetFunction",
                "lambda:ListFunctions"
            ],
            "Resource": [
                "arn:aws:lambda:*:*:function:*SageMaker*",
                "arn:aws:lambda:*:*:function:*sagemaker*",
                "arn:aws:lambda:*:*:function:*Sagemaker*"
            ]
        },
        {
            "Sid": "LambdaLayerForAWSSDK",
            "Effect": "Allow",
            "Action": ["lambda:GetLayerVersion"],
            "Resource": ["arn:aws:lambda:*:336392948345:layer:AWSSDK*"]
        },
        {
            "Sid": "BedrockDeploy",
            "Effect": "Allow",
            "Action": [
                "bedrock:CreateModelImportJob",
                "bedrock:GetModelImportJob",
                "bedrock:GetImportedModel",
                "bedrock:ListProvisionedModelThroughputs",
                "bedrock:ListCustomModelDeployments",
                "bedrock:ListCustomModels",
                "bedrock:ListModelImportJobs",
                "bedrock:GetEvaluationJob",
                "bedrock:CreateEvaluationJob",
                "bedrock:InvokeModel",
                "bedrock:GetFoundationModelAvailability",
                "bedrock:ListFoundationModels"
            ],
            "Resource": ["*"]
        },
        {
            "Sid": "AIRegistry",
            "Effect": "Allow",
            "Action": [
                "sagemaker:CreateHub",
                "sagemaker:DeleteHub",
                "sagemaker:DescribeHub",
                "sagemaker:ListHubs",
                "sagemaker:ImportHubContent",
                "sagemaker:DeleteHubContent",
                "sagemaker:UpdateHubContent",
                "sagemaker:ListHubContents",
                "sagemaker:ListHubContentVersions",
                "sagemaker:DescribeHubContent"
            ],
            "Resource": "*"
        },
        {
            "Sid": "ModelPackageAccess",
            "Effect": "Allow",
            "Action": [
                "sagemaker:CreateModelPackage",
                "sagemaker:DescribeModelPackage",
                "sagemaker:ListModelPackages",
                "sagemaker:CreateModelPackageGroup",
                "sagemaker:DescribeModelPackageGroup",
                "sagemaker:ListModelPackageGroups",
                "sagemaker:CreateModel"
            ],
            "Resource": ["*"]
        }
    ]
}
```


## Dataset Formats

### SFT Dataset Format

JSONL with prompt-completion pairs:

```json
{
    "prompt": "Given a table and relevant text descriptions, answer the following question.\n\nTable:\n...\n\nQuestion: How many business segments were present in 2019 and 2018?\n\nAnswer:",
    "completion": "one",
    "data_idx": "2951"
}
```

### DPO Dataset Format

JSONL with preferred and rejected responses:

```json
{
    "source": "evol_instruct",
    "prompt": "Can you write a C++ program that...",
    "chosen": "Here's a C++ program that prompts the user...",
    "chosen-rating": 5.0,
    "chosen-model": "starchat",
    "rejected": "Sure, here is the program using...",
    "rejected-rating": 1.25,
    "rejected-model": "pythia-12b"
}
```

### RLVR Dataset Format (Verl format)

JSONL with prompts and ground truth for reward function scoring:

```json
{
    "data_source": "custom",
    "prompt": [
        {"role": "system", "content": "You are a helpful assistant. When using tools, respond with: [...]"},
        {"role": "user", "content": "Get weather for San Francisco"}
    ],
    "ability": "tool-calling",
    "reward_model": {
        "ground_truth": "[{\"name\": \"get_weather_forecast\", \"arguments\": {\"city\": \"San Francisco\"}}]"
    }
}
```

For math/reasoning tasks:

```json
{
    "data_source": "openai/gsm8k",
    "prompt": [
        {"role": "system", "content": "You are a helpful math tutor..."},
        {"role": "user", "content": "Natalia sold clips to 48 of her friends in April..."}
    ],
    "ability": "math",
    "extra_info": {
        "answer": "Natalia sold 48/2 = 24 clips in May.\nNatalia sold 48+24 = 72 clips altogether.\n#### 72",
        "index": 0,
        "question": "Natalia sold clips to 48 of her friends in April...",
        "split": "train"
    },
    "reward_model": {
        "ground_truth": "72"
    }
}
```

Note: When both `extra_info.answer` and `reward_model.ground_truth` are present, `extra_info.answer` takes precedence.

### RLAIF Dataset Formats

Pairwise judging:

```json
{
    "data_source": "WeOpenML/PandaLM",
    "prompt": [
        {
            "role": "user",
            "content": "Below are two responses for a given task...\n\n### Response 1:\n...\n\n### Response 2:\n...\n\n### Evaluation:\n"
        }
    ],
    "ability": "pairwise-judging",
    "reward_model": {
        "style": "llmj",
        "ground_truth": "2\n\n### Reason: Response 2 provides a more detailed comparison..."
    }
}
```

Chain of thought:

```json
{
    "data_source": "openai/gsm8k",
    "prompt": [
        {"role": "system", "content": "You are an AI assistant that uses a Chain of Thought (CoT) approach..."},
        {"role": "user", "content": "A craft store makes a third of its sales in the fabric section..."}
    ],
    "ability": "chain-of-thought",
    "reward_model": {
        "style": "llmj-cot",
        "ground_truth": "Thus, there were 36 - 12 - 9 = 15 sales in the stationery section."
    }
}
```

Other RLAIF abilities: `faithfulness`, `summarization`, `custom-prompt`.

### Evaluation Dataset Formats

Five formats are supported for evaluation datasets:

1. OpenAI format (`messages` array with system/user/assistant roles)
2. SageMaker Evaluation format (`system`, `query`, `response`, `category`)
3. HuggingFace Prompt-Completion (`prompt`, `completion`)
4. HuggingFace Preference (`prompt`, `chosen`, `rejected`)
5. Verl format (same as RLVR training format)

---

## SDK v3 — Model Customization Trainers

### Creating Assets (Datasets and Evaluators)

Before submitting a customization job, register your dataset and evaluators:

```python
from sagemaker.assets import DataSet
from sagemaker.train.common import CustomizationTechnique

# Create a dataset asset
dataset = DataSet.create(
    name="my-sft-dataset",
    data_location="s3://my-bucket/datasets/training-data.jsonl",
    customization_technique=CustomizationTechnique.SFT,
    wait=True,
)
print(f"Dataset ARN: {dataset.arn}")
```

For evaluators (reward functions):

```python
from sagemaker.ai_registry.evaluator import Evaluator
from sagemaker.ai_registry.air_constants import REWARD_FUNCTION

# From a Lambda ARN
evaluator = Evaluator.create(
    name="my-reward-function",
    source="arn:aws:lambda:us-west-2:123456789012:function:my-reward-fn",
    type=REWARD_FUNCTION,
)

# From local Python file (auto-creates Lambda)
evaluator = Evaluator.create(
    name="my-reward-function",
    source="./reward_function.py",
    type=REWARD_FUNCTION,
)

# For RLAIF reward prompts, use REWARD_PROMPT type:
# from sagemaker.ai_registry.air_constants import REWARD_PROMPT
# evaluator = Evaluator.create(name="my-judge-prompt", source="Evaluate...", type=REWARD_PROMPT)

evaluator.wait()
evaluator.refresh()
```

### SFT Training Job

```python
from sagemaker.train import SFTTrainer
from sagemaker.train.common import TrainingType

trainer = SFTTrainer(
    model="meta-llama/Llama-3.1-8B-Instruct",  # Must be a supported model
    training_type=TrainingType.LORA,
    model_package_group_name="my-custom-models",
    training_dataset="s3://my-bucket/datasets/sft-data.jsonl",
    s3_output_path="s3://my-bucket/output/",
    sagemaker_session=sagemaker_session,
    role=role_arn,
)

training_job = trainer.train()
```

### DPO Training Job

```python
from sagemaker.train import DPOTrainer
from sagemaker.train.common import TrainingType

trainer = DPOTrainer(
    model="meta-llama/Llama-3.1-8B-Instruct",
    training_type=TrainingType.LORA,
    model_package_group_name="my-custom-models",
    training_dataset="s3://my-bucket/datasets/dpo-data.jsonl",
    s3_output_path="s3://my-bucket/output/",
    sagemaker_session=sagemaker_session,
    role=role_arn,
)

training_job = trainer.train()
```

### RLVR Training Job

```python
from sagemaker.train import RLVRTrainer
from sagemaker.train.common import TrainingType

trainer = RLVRTrainer(
    model="Qwen/Qwen2.5-7B-Instruct",
    training_type=TrainingType.LORA,
    model_package_group_name="my-custom-models",
    training_dataset="s3://my-bucket/datasets/rlvr-data.jsonl",
    reward_function="arn:aws:lambda:us-east-1:123456789012:function:my-reward-fn",
    s3_output_path="s3://my-bucket/output/",
    sagemaker_session=sagemaker_session,
    role=role_arn,
)

training_job = trainer.train()
```

### RLAIF Training Job

RLAIF uses an AI judge model (from Bedrock) instead of a Lambda reward function:

```python
from sagemaker.train import RLAIFTrainer
from sagemaker.train.common import TrainingType

trainer = RLAIFTrainer(
    model="meta-llama/Llama-3.1-8B-Instruct",
    training_type=TrainingType.LORA,
    model_package_group_name="my-custom-models",
    training_dataset="s3://my-bucket/datasets/rlaif-data.jsonl",
    reward_prompt="Evaluate the response for helpfulness, accuracy, and safety...",
    s3_output_path="s3://my-bucket/output/",
    sagemaker_session=sagemaker_session,
    role=role_arn,
)

training_job = trainer.train()
```

### Common Trainer Parameters

| Parameter | Description | Required |
|-----------|-------------|----------|
| `model` | Base model ID (must be from supported list) | Yes |
| `training_type` | `TrainingType.LORA` or `TrainingType.FULL` | Yes |
| `model_package_group_name` | Model registry group for output | Yes |
| `training_dataset` | S3 URI to JSONL training data | Yes |
| `s3_output_path` | S3 URI for output artifacts | Yes |
| `role` | IAM execution role ARN | Yes |
| `sagemaker_session` | SageMaker session object | Yes |
| `reward_function` | Lambda ARN (RLVR only) | RLVR only |
| `reward_prompt` | Judge prompt text (RLAIF only) | RLAIF only |

### Hyperparameters

Configurable via the Studio UI or SDK. Key hyperparameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| Batch size | Model-dependent | Training batch size |
| Learning rate | 5e-6 | Optimizer learning rate |
| Number of epochs | 3 | Training epochs |
| Rollouts per prompt | 8 | RLVR/RLAIF: candidates generated per prompt for GRPO |

Hyperparameters can be passed as keyword arguments to the trainer. Consult the SageMaker Studio UI for the full list of configurable hyperparameters per technique — the UI shows recommended values and valid ranges when you select a model and technique.

### Dataset Size Guidelines

| Technique | Minimum Examples | Recommended | Notes |
|-----------|-----------------|-------------|-------|
| SFT | ~100 | 1,000–10,000 | More data generally improves quality |
| DPO | ~100 | 1,000–5,000 | Each example needs chosen + rejected |
| RLVR | ~500 | 1,000–5,000 | Needs diverse prompts for GRPO exploration |
| RLAIF | ~500 | 1,000–5,000 | Similar to RLVR |

Dataset sizes are model-dependent. Larger models may need fewer examples. Start small, evaluate, and iterate.

---

## RLVR Reward Functions

### Lambda Reward Function Contract

Your Lambda function receives batches of samples and must return scores:

Input payload:
```json
[
    {
        "id": "123",
        "messages": [
            {"role": "user", "content": "Get weather for San Francisco"},
            {"role": "assistant", "content": "[{\"name\": \"get_weather_forecast\", \"arguments\": {\"city\": \"San Francisco\"}}]"}
        ],
        "reference_answer": {
            "ground_truth": "[{\"name\": \"get_weather_forecast\", \"arguments\": {\"city\": \"San Francisco\"}}]"
        }
    }
]
```

Required output:
```json
[
    {
        "id": "123",
        "aggregate_reward_score": 1.0,
        "metrics_list": [
            {"name": "tool_name_match", "value": 1.0, "type": "Reward"},
            {"name": "args_match", "value": 1.0, "type": "Metric"}
        ]
    }
]
```

### Built-in Scorers

Two built-in scorers are available for evaluation:
- `PRIME_MATH` — Scores math answers against ground truth
- `PRIME_CODE` — Executes generated code against test cases

### Example: Tool Calling Reward Function

```python
import json

def lambda_handler(event, context):
    return lambda_grader(event)

def lambda_grader(samples):
    results = []
    for sample in samples:
        sample_id = sample.get("id", "")
        messages = sample.get("messages", [])
        reference = sample.get("reference_answer", {})
        ground_truth = reference.get("ground_truth", "")

        # Extract assistant response
        assistant_msg = ""
        for msg in messages:
            if msg.get("role") == "assistant":
                assistant_msg = msg.get("content", "")

        score = compute_tool_call_score(assistant_msg, ground_truth)

        results.append({
            "id": sample_id,
            "aggregate_reward_score": score,
            "metrics_list": [
                {"name": "tool_call_reward", "value": score, "type": "Reward"}
            ],
        })
    return results

def compute_tool_call_score(prediction, ground_truth):
    """Score tool call predictions against ground truth.
    Returns 1.0 for perfect match, 0.5 for partial, 0.0 for wrong."""
    try:
        pred_tools = json.loads(prediction)
        gt_tools = json.loads(ground_truth)
    except (json.JSONDecodeError, TypeError):
        # If ground truth is not JSON, it's a clarification/refusal case
        # Check if model also avoided tool calls
        if not _looks_like_tool_call(prediction):
            return 0.5  # Model correctly avoided calling a tool
        return 0.0

    if not isinstance(pred_tools, list):
        pred_tools = [pred_tools]
    if not isinstance(gt_tools, list):
        gt_tools = [gt_tools]

    pred_names = {t.get("name", "") for t in pred_tools}
    gt_names = {t.get("name", "") for t in gt_tools}

    if pred_names == gt_names:
        # Right function(s) — check arguments
        perfect = True
        for pt in pred_tools:
            for gt in gt_tools:
                if pt.get("name") == gt.get("name"):
                    if pt.get("arguments") != gt.get("arguments"):
                        perfect = False
        return 1.0 if perfect else 0.5
    elif pred_names & gt_names:
        return 0.5  # Partial overlap
    else:
        return 0.0  # Wrong function

def _looks_like_tool_call(text):
    return "[{" in text or "TOOLCALL" in text.upper()
```

---

## Model Evaluation

After training, evaluate your customized model. Three evaluation approaches are available:

### 1. Benchmark Evaluation

Evaluate against standardized benchmarks:

| Benchmark | Description | Metrics | Strategy |
|-----------|-------------|---------|----------|
| MMLU | Multi-task Language Understanding (57 subjects) | accuracy | zs_cot |
| MMLU_PRO | Professional subset (law, medicine, engineering) | accuracy | zs_cot |
| BBH | Advanced reasoning tasks | accuracy | fs_cot |
| GPQA | General Physics QA | accuracy | zs_cot |
| MATH | Mathematical problem solving | exact_match | zs_cot |
| StrongReject | Safety — detect/reject harmful content | deflection | zs |
| IFEval | Instruction-following evaluation | accuracy | zs |

```python
from sagemaker.train.evaluate import BenchMarkEvaluator, get_benchmarks

Benchmark = get_benchmarks()

evaluator = BenchMarkEvaluator(
    benchmark=Benchmark.MMLU,
    model="arn:aws:sagemaker:<region>:<account-id>:model-package/<name>/<version>",
    s3_output_path="s3://my-bucket/eval/",
    evaluate_base_model=False,  # Set True to compare against base model
)

execution = evaluator.evaluate()
execution.wait(target_status="Succeeded", poll=5, timeout=3600)
execution.show_results()
```

### 2. LLM-as-a-Judge (LLMAJ) Evaluation

Use a Bedrock foundation model to grade your model's responses:

```python
from sagemaker.train.evaluate import LLMAsJudgeEvaluator

# With built-in metrics
evaluator = LLMAsJudgeEvaluator(
    model="arn:aws:sagemaker:<region>:<account-id>:model-package/<name>/<version>",
    evaluator_model="<bedrock-judge-model-id>",
    dataset="s3://my-bucket/eval-data.jsonl",
    builtin_metrics=["helpfulness", "correctness"],
    s3_output_path="s3://my-bucket/eval/",
    evaluate_base_model=False,
)

execution = evaluator.evaluate()
```

With custom metrics:

```python
custom_metric = {
    "customMetricDefinition": {
        "name": "PositiveSentiment",
        "instructions": (
            "You are an expert evaluator. Rate the response based on whether "
            "it conveys positive sentiment, helpfulness, and constructive tone.\n\n"
            "Rate on this scale:\n"
            "- Good: Response has positive sentiment\n"
            "- Poor: Response lacks positive sentiment\n\n"
            "Prompt: {{prompt}}\n"
            "Response: {{prediction}}"
        ),
        "ratingScale": [
            {"definition": "Good", "value": {"floatValue": 1}},
            {"definition": "Poor", "value": {"floatValue": 0}},
        ],
    }
}

evaluator = LLMAsJudgeEvaluator(
    model="arn:aws:sagemaker:<region>:<account-id>:model-package/<name>/<version>",
    evaluator_model="<bedrock-judge-model-id>",
    dataset="s3://my-bucket/eval-data.jsonl",
    custom_metrics=custom_metric,
    s3_output_path="s3://my-bucket/eval/",
    evaluate_base_model=False,
)

execution = evaluator.evaluate()
```

### 3. Custom Scorer Evaluation

Use built-in scorers (Prime Math, Prime Code) or your own Lambda:

```python
from sagemaker.train.evaluate import CustomScorerEvaluator, get_builtin_metrics

BuiltInMetric = get_builtin_metrics()

# Built-in scorer
evaluator = CustomScorerEvaluator(
    evaluator=BuiltInMetric.PRIME_MATH,
    dataset="arn:aws:sagemaker:<region>:<account-id>:hub-content/<id>/DataSet/<name>/<version>",
    model="arn:aws:sagemaker:<region>:<account-id>:model-package/<name>/<version>",
    s3_output_path="s3://my-bucket/eval/",
    evaluate_base_model=False,
)

execution = evaluator.evaluate()
```

For custom Lambda scorer, provide the Lambda ARN as the evaluator.

---

## Model Deployment

After customization and evaluation, deploy your model to either SageMaker AI inference or Amazon Bedrock.

### Deploy to SageMaker AI Inference

Use the standard SageMaker deployment patterns from `inference-endpoints.md`. The customized model is registered as a Model Package in the SageMaker Model Registry. Deploy it using the Core API:

```python
from sagemaker.core.resources import Model, EndpointConfig, Endpoint
from sagemaker.core.shapes.shapes import ContainerDefinition, ProductionVariant

# The model artifacts are in S3 from the training job output
Model.create(
    model_name="my-custom-model",
    primary_container=ContainerDefinition(
        image=f"763104351884.dkr.ecr.{region}.amazonaws.com/djl-inference:0.36.0-lmi20.0.0-cu128",
        model_data_url="s3://my-bucket/output/<training-job>/output/model.tar.gz",
        environment={
            "OPTION_ROLLING_BATCH": "vllm",
            "OPTION_DTYPE": "fp16",
            "OPTION_MAX_MODEL_LEN": "4096",
            "OPTION_TENSOR_PARALLEL_DEGREE": "1",
        },
    ),
    execution_role_arn=role_arn,
)

EndpointConfig.create(
    endpoint_config_name="my-custom-endpoint",
    production_variants=[ProductionVariant(
        variant_name="AllTraffic",
        model_name="my-custom-model",
        initial_instance_count=1,
        instance_type="ml.g5.2xlarge",
        initial_variant_weight=1.0,
        container_startup_health_check_timeout_in_seconds=900,
    )],
)

Endpoint.create(
    endpoint_name="my-custom-endpoint",
    endpoint_config_name="my-custom-endpoint",
)
```

### Deploy to Amazon Bedrock

From the SageMaker Studio UI, choose Deploy > Bedrock on your custom model details page. This triggers a Bedrock Custom Model Import job. Programmatically:

```python
import boto3

bedrock = boto3.client("bedrock", region_name="us-east-1")

response = bedrock.create_model_import_job(
    jobName="import-my-custom-model",
    importedModelName="my-custom-model",
    roleArn=role_arn,
    modelDataSource={
        "s3DataSource": {
            "s3Uri": "s3://my-bucket/output/<training-job>/output/model/"
        }
    },
)
```

---

## End-to-End Workflow Example: RLVR for Tool Calling

This example fine-tunes Qwen 2.5 7B Instruct for agentic tool calling using RLVR.

### Step 1: Prepare Training Data

Create a JSONL file with three behavior types — tool execution, clarification, and refusal:

```python
import json

training_data = [
    # Tool execution — user provides all required params
    {
        "prompt": [
            {"role": "system", "content": "You are a helpful assistant with access to tools. When calling a tool, respond with JSON: [{\"name\": \"tool_name\", \"arguments\": {...}}]"},
            {"role": "user", "content": "What's the weather in Seattle?"}
        ],
        "reward_model": {
            "ground_truth": '[{"name": "get_weather", "arguments": {"city": "Seattle"}}]'
        }
    },
    # Clarification — missing required parameter
    {
        "prompt": [
            {"role": "system", "content": "You are a helpful assistant with access to tools..."},
            {"role": "user", "content": "Check the weather"}
        ],
        "reward_model": {
            "ground_truth": "Could you please specify which city you'd like the weather for?"
        }
    },
    # Multi-parameter tool call
    {
        "prompt": [
            {"role": "system", "content": "You are a helpful assistant with access to tools..."},
            {"role": "user", "content": "Convert 100 USD to EUR"}
        ],
        "reward_model": {
            "ground_truth": '[{"name": "currency_convert", "arguments": {"amount": 100, "from": "USD", "to": "EUR"}}]'
        }
    },
]

with open("training_data.jsonl", "w") as f:
    for sample in training_data:
        f.write(json.dumps(sample) + "\n")

# Upload to S3
import boto3
s3 = boto3.client("s3")
s3.upload_file("training_data.jsonl", "my-bucket", "datasets/rlvr-tool-calling.jsonl")
```

### Step 2: Create Reward Function

Deploy the tool calling reward function as a Lambda (see the reward function example above).

### Step 3: Register Assets

```python
from sagemaker.assets import DataSet
from sagemaker.train.common import CustomizationTechnique
from sagemaker.ai_registry.evaluator import Evaluator
from sagemaker.ai_registry.air_constants import REWARD_FUNCTION

dataset = DataSet.create(
    name="tool-calling-rlvr-dataset",
    data_location="s3://my-bucket/datasets/rlvr-tool-calling.jsonl",
    customization_technique=CustomizationTechnique.RLVR,
    wait=True,
)

evaluator = Evaluator.create(
    name="tool-calling-reward",
    source="arn:aws:lambda:us-east-1:123456789012:function:tool-call-reward",
    type=REWARD_FUNCTION,
)
evaluator.wait()
```

### Step 4: Submit Training Job

```python
from sagemaker.train import RLVRTrainer
from sagemaker.train.common import TrainingType
from sagemaker.core.helper.session_helper import Session, get_execution_role

session = Session()
role = get_execution_role()

trainer = RLVRTrainer(
    model="Qwen/Qwen2.5-7B-Instruct",
    training_type=TrainingType.LORA,
    model_package_group_name="tool-calling-models",
    training_dataset="s3://my-bucket/datasets/rlvr-tool-calling.jsonl",
    reward_function="arn:aws:lambda:us-east-1:123456789012:function:tool-call-reward",
    s3_output_path="s3://my-bucket/output/",
    sagemaker_session=session,
    role=role,
)

training_job = trainer.train()
```

### Step 5: Evaluate

```python
from sagemaker.train.evaluate import BenchMarkEvaluator, get_benchmarks

Benchmark = get_benchmarks()

evaluator = BenchMarkEvaluator(
    benchmark=Benchmark.MMLU,
    model=training_job.model_package_arn,  # From training output
    s3_output_path="s3://my-bucket/eval/",
    evaluate_base_model=True,  # Compare against base model
)

execution = evaluator.evaluate()
execution.wait(target_status="Succeeded", poll=5, timeout=3600)
execution.show_results()
```

### Step 6: Deploy

Deploy to SageMaker inference or Bedrock (see deployment section above).

---

## Monitoring Training Jobs

Training metrics are automatically logged to serverless MLflow. Key metrics to watch:

| Metric | What It Tells You |
|--------|-------------------|
| Train Reward (RLVR/RLAIF) | Should increase over training steps |
| Policy Entropy | Should decrease (model getting more confident) |
| Gradient Norm | Should stabilize (updates getting refined) |
| Mean Advantage Estimate | Should converge toward zero |
| Training Loss (SFT/DPO) | Should decrease over epochs |

Access MLflow from the SageMaker Studio training job details page.

---

## When to Use Serverless Model Customization vs Other Approaches

| Criteria | Serverless Model Customization | SageMaker Training Jobs | SageMaker HyperPod |
|----------|-------------------------------|------------------------|-------------------|
| Best for | Quick fine-tuning, no infra management | Flexible training with cost control | Large-scale, long-running FM training |
| Supported models | Specific supported list only | Any model | Any model |
| Infrastructure | Fully managed, serverless | Ephemeral instances | Persistent cluster |
| Cost model | Pay-per-token | Pay-per-hour | Pay for cluster uptime |
| Techniques | SFT, DPO, RLVR, RLAIF | Any (bring your own script) | Any |
| Evaluation | Built-in (benchmarks, LLMAJ, custom scorers) | Manual | Manual |
| Deployment | One-click to SageMaker or Bedrock | Manual | Manual |
| Complexity | Low | Medium | High |

Use Serverless Model Customization when:
- Your model is on the supported list
- You want the fastest path from data to deployed model
- You don't need SSH access to training instances
- You want built-in evaluation and deployment

Use SageMaker Training Jobs when:
- Your model is NOT on the supported list
- You need custom training scripts or frameworks
- You need full control over the training environment
- You want to use Spot instances for cost savings

---

## Troubleshooting

### Training job fails with unsupported model error
- Verify the model is on the supported models list (see table above)
- Check the exact model ID spelling — it must match exactly
- Some models are region-dependent; verify availability in your region

### Reward function Lambda timeout
- Default Lambda timeout is 15 minutes; increase if processing large batches
- Ensure your Lambda has sufficient memory (512MB+ recommended)
- Check CloudWatch logs: `/aws/lambda/<function-name>`

### Training metrics not appearing in MLflow
- MLflow integration is automatic — wait a few minutes after job starts
- Check that your execution role has MLflow permissions
- Verify the MLflow app is running in your SageMaker domain

### Evaluation job fails
- Ensure the model package ARN is correct and the model is registered
- Check that the evaluation dataset format matches one of the supported formats
- For custom scorers, verify Lambda permissions and test the function independently

### Deployment to Bedrock fails
- Ensure your execution role has `bedrock:CreateModelImportJob` permission
- Verify the model artifacts are in the expected S3 location
- Check Bedrock console for import job status and error details

## Reference Links

- Product page: https://aws.amazon.com/sagemaker/ai/model-customization/
- Documentation: https://docs.aws.amazon.com/sagemaker/latest/dg/model-customize-open-weight.html
- SDK docs: https://sagemaker.readthedocs.io/en/stable/model_customization/index.html
- March 2026 model expansion: https://aws.amazon.com/about-aws/whats-new/2026/03/amazon-sagemaker-ai-serverless-additional-models/
- RLVR walkthrough: https://builder.aws.com/content/3BS29S01H2GBPV9ebnwH8H1v11G/serverless-model-customization-with-rlvr-in-amazon-sagemaker-ai
- Dataset formats: https://docs.aws.amazon.com/sagemaker/latest/dg/model-customize-evaluation-dataset-formats.html
- Pricing: https://aws.amazon.com/sagemaker/ai/pricing/
