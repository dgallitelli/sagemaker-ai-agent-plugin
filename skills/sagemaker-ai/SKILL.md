---
name: sagemaker-ai
description: Build, train, deploy, monitor, or troubleshoot workloads on Amazon SageMaker AI. Use for SageMaker Python SDK v3, model training and customization, inference, HyperPod, Model Monitor, AutoGluon, Pipelines, or iterative training with managed warm pools.
---

# Amazon SageMaker AI

Produce practical, current SageMaker AI implementations using the Python SDK v3, AWS CLI, boto3, and the optional official AWS Labs SageMaker AI MCP server.

Read only the references relevant to the request. Do not load every reference by default.

## Operating rules

- Use SageMaker Python SDK v3. Do not emit v2 estimator, model, processing, transformer, or pipeline imports.
- For infrastructure work, inspect the account with read-only AWS CLI calls before changing CDK, Terraform, or CloudFormation.
- Check current official AWS documentation, DLC listings, instance availability, quotas, and model compatibility when the answer can change over time.
- Never hardcode credentials, account IDs, role ARNs, or private local paths.
- Obtain authorization immediately before mutating or deleting AWS resources.
- Clean up endpoints, training warm pools, clusters, and other chargeable resources when the requested workflow is complete.
- When a request implies two or more sequential training jobs using the same instance configuration, use the managed warm-pool workflow unless the user declines.

## Route the request

| Intent | Read |
|---|---|
| Exact SDK v3 imports, classes, signatures, or migration | `references/sdk-v3-reference.md` |
| Classical training, HPO, distributed training, local mode, or processing | `references/sdk-v3/training-patterns.md` |
| Classical inference, JumpStart, ModelBuilder, or batch transform | `references/sdk-v3/inference-patterns.md` |
| LLM endpoints, DJL LMI, vLLM, containers, or CUDA compatibility | `references/inference-endpoints.md` and `references/sdk-v3/llm-inference-patterns.md` |
| SageMaker Pipelines or workflow DAGs | `references/sdk-v3/pipeline-patterns.md` |
| Serverless SFT, DPO, RLVR, RLAIF, evaluation, or reward functions | `references/model-customization.md` |
| Custom-script LLM training, LoRA, QLoRA, DPO, CPT, GPU, or Trainium | `references/llm-training/best-practices.md`, then the relevant file under `references/llm-training/` |
| General training-job launcher or recipe patterns | `references/training-jobs.md` and `references/sdk-v3/llm-training-patterns.md` |
| HyperPod cluster creation or operations | `references/hyperpod.md`, then the relevant file under `references/hyperpod/` |
| HyperPod inference | `references/hyperpod-inference.md` |
| Model Monitor, data quality, model quality, bias, or explainability | `references/model-monitor.md` |
| AutoGluon, AutoML, tabular, time-series, or multimodal workflows | `references/automl-autogluon.md` |
| Repeated training, sweeps, dependency iteration, or train-until-metric loops | `references/warm-pool-iteration.md` |

## SDK v3 baseline

Use the current package layout:

```python
from sagemaker.core.helper.session_helper import Session, get_execution_role
from sagemaker.core.training.configs import Compute, OutputDataConfig, SourceCode
from sagemaker.train import ModelTrainer
from sagemaker.serve import ModelBuilder
```

For serverless model customization:

```python
from sagemaker.train import DPOTrainer, RLAIFTrainer, RLVRTrainer, SFTTrainer
```

Consult `references/sdk-v3-reference.md` before generating substantial SDK code.

## Optional MCP integration

The bundled `mcp.json` starts the official `awslabs.sagemaker-ai-mcp-server` package without write-access flags.

- Use it for supported HyperPod discovery and operations.
- Do not assume it covers every SageMaker API.
- Use read-only AWS CLI or SDK discovery for capabilities not exposed by the server.
- Do not enable MCP write or sensitive-data access without explicit user authorization.

## Reusable resources

- General templates: `templates/`
- LLM training templates: `templates/llm-training/`
- HyperPod configuration assets: `assets/hyperpod/`
- LLM inspection and dataset scripts: `scripts/llm-training/`
- HyperPod validation and diagnostic scripts: `scripts/hyperpod/`

Adapt templates to the user’s repository and environment. Do not copy examples without checking their assumptions.

## Before delivery

- Confirm all imports are SDK v3.
- Match containers and CUDA versions to the selected instance.
- Match input-channel names between launchers and training scripts.
- Save model artifacts under `/opt/ml/model/`.
- Use `wait=True, logs=True` for interactive training workflows.
- Confirm region-specific quotas and availability.
- Include cleanup for persistent or billable resources.
