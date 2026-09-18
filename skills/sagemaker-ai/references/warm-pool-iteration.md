# Warm Pool Iteration — Orchestration Skill

This capability is also available as the independently installable
`sagemaker-warm-pool-researcher` skill. Keep that repository standalone while
maintaining equivalent warm-pool behavior in this unified package.

You are managing an iterative SageMaker training loop that reuses a managed warm pool
between submissions. Your job is to maintain pool affinity across iterations, fail fast
on breakage, and release the instance when done.

---

## 0. Auto-Detection (Read This First)

**This skill applies any time the user's request will produce 2+ sequential SageMaker
training jobs on the same instance type.** You do not need the user to say "warm pool."

### Patterns that signal warm pool candidacy

| Pattern | Example |
|---------|---------|
| Hyperparameter sweep | "Try learning rates 1e-4, 5e-5, 2e-5" |
| Train-until-metric | "Train until eval loss < 0.3" or "iterate until accuracy > 90%" |
| Dependency debugging | "Bump transformers and retrain" or "fix the import error and rerun" |
| Recipe iteration | "Try LoRA rank 16, then 32, then 64" |
| Ablation study | "Run with and without gradient checkpointing" |
| Config grid | "Try batch sizes 4, 8, 16 on this setup" |

### What to do when you detect a candidate

1. Inform the user: "This looks like it will take multiple training iterations on the
   same instance — I'll use a managed warm pool to avoid repeated cold starts."
2. Activate this skill's full workflow (quota check → locked fields → iteration loop → cleanup).
3. If the user declines, skip warm pools and submit jobs normally.

### When NOT to auto-activate

- Single training job with no iteration intent
- User explicitly asks for spot instances (incompatible)
- Heterogeneous cluster request
- Serverless Model Customization (warm pools don't apply)

---

## 1. Pre-Flight Checks (Run Once at Loop Start)

Before submitting the first training job:

### Quota verification
Each instance type has its own warm pool quota code. Find yours by filtering:
```bash
aws service-quotas list-service-quotas \
  --service-code sagemaker \
  --region <region> \
  --query "Quotas[?contains(QuotaName, 'warm pool') && contains(QuotaName, '<instance-type>')].[QuotaCode,Value,QuotaName]" \
  --output table
```
If `Value` is 0: STOP. Inform the user that warm pool quota must be requested for the
target instance type. The keep-alive parameter silently no-ops without quota — jobs will
succeed but cold-start every time.

### Lock the immutable fields
These fields MUST remain identical across ALL iterations or the pool breaks.
Record them at job 1 and never change them:

| Field | Source |
|-------|--------|
| `RoleArn` | IAM execution role |
| `ResourceConfig.InstanceType` | e.g. `ml.g6e.2xlarge` |
| `ResourceConfig.InstanceCount` | e.g. `1` |
| `ResourceConfig.VolumeSizeInGB` | e.g. `250` |
| `ResourceConfig.VolumeKmsKeyId` | KMS key ARN (or absent) |
| `VpcConfig.SecurityGroupIds` | List of SG IDs (or absent) |
| `VpcConfig.Subnets` | List of subnet IDs (or absent) |
| `EnableInterContainerTrafficEncryption` | bool |
| `EnableNetworkIsolation` | bool |
| Session tags (if `EnableSessionTagChaining=True`) | tag key set |

### Fields you CAN change freely between iterations
- Hyperparameters
- Training script / source directory
- Input data channels
- Output S3 path
- Job name (must be unique per job)
- Environment variables
- `KeepAlivePeriodInSeconds` value (inherited fresh each job)

---

## 2. Job Submission Template

```python
from sagemaker.train.model_trainer import ModelTrainer
from sagemaker.train.configs import Compute, InputData, OutputDataConfig, SourceCode

trainer = ModelTrainer(
    training_image=IMAGE_URI,
    source_code=SourceCode(
        source_dir="src/",
        entry_script="train.py",
    ),
    compute=Compute(
        instance_type="ml.g6e.2xlarge",      # LOCKED
        instance_count=1,                     # LOCKED
        volume_size_in_gb=250,                # LOCKED
        keep_alive_period_in_seconds=1800,    # 30 min default; adjust per cadence
    ),
    output_data_config=OutputDataConfig(s3_output_path=OUTPUT_PATH),
    hyperparameters={...},                    # FREE — change every iteration
    environment={
        "PIP_CACHE_DIR": "/opt/ml/sagemaker/warmpoolcache/pip",
    },
    role=ROLE_ARN,                            # LOCKED
)
trainer.train(wait=True, logs=True)
```

### Why `wait=True, logs=True`
- Fail-fast: error appears in-shell immediately, no CloudWatch polling
- Agent can parse the failure and patch within seconds
- Billing stops when the training step ends (pool enters Available)

### Persistent cache
The directory `/opt/ml/sagemaker/warmpoolcache` (env var
`SAGEMAKER_MANAGED_WARMPOOL_CACHE_DIRECTORY`) survives across jobs on the same pool.
Use it for:
- pip/conda package cache (set `PIP_CACHE_DIR` environment variable)
- Model checkpoints for incremental training
- Downloaded datasets that don't change between iterations
- Any artifact expensive to recreate

---

## 3. Between Iterations (Verify Before Resubmit)

After each completed job, before submitting the next:

```bash
aws sagemaker describe-training-job \
  --training-job-name <previous-job-name> \
  --query "WarmPoolStatus"
```

| Status | Meaning | Action |
|--------|---------|--------|
| `Available` | Pool is hot, waiting for next match | Submit next job — will reuse |
| `Reused` | Pool moved to a different job | Expected on the job BEFORE current |
| `InUse` | Currently running a job | Wait — don't submit a competing job |
| `Terminated` | Pool died | Next job will cold-start. Investigate why. |

### Pool death causes
- **InternalServerError** during previous job (infrastructure failure)
- **Explicit stop** (`StopTrainingJob` or `KeepAlivePeriodInSeconds=0`)
- **Keep-alive expiry** (exceeded the configured seconds with no matching job)
- **Patch update** to the cluster
- **Mismatched fields** — next job didn't match on a LOCKED field

If `Terminated`: warn the user, note the cold-start cost, and continue. The next job
with `keep_alive_period_in_seconds > 0` will create a new pool.

---

## 4. Iteration Loop (Agent Behavior)

```
┌─────────────────────────────────────────────────┐
│ 1. Submit training job (LOCKED fields constant) │
│ 2. wait=True, logs=True → block until complete  │
│ 3. Job succeeded?                               │
│    YES → Go to CLEANUP                          │
│    NO  → Read failure from logs                 │
│ 4. Is the failure recoverable by patching?      │
│    NO  → Go to CLEANUP                          │
│    YES → Patch code/config                      │
│ 5. Verify WarmPoolStatus == Available           │
│    If Terminated → warn, continue (cold start)  │
│    Go to step 1                                 │
│                                                 │
│ CLEANUP (always runs on any exit path):         │
│    Release warm pool → EXIT                     │
└─────────────────────────────────────────────────┘
```

**The agent MUST release the warm pool on every exit path** — success, unrecoverable
failure, or decision to stop iterating. The only exception is a hard crash of the
agent process itself (in which case the keep-alive expiry is the safety net).

### Tight-loop economics
At ~90s agent turnaround between jobs:
- 7 iterations ≈ 28 min wall-clock, ~$1.31 (ml.g6e.2xlarge)
- Same 7 iterations cold: 58 min, ~$2.29
- Savings: 43% cost, 2.4x faster, single capacity acquisition

### Keep-alive tuning
- Default `1800` (30 min) is safe for human-driven iteration
- For agent-driven tight loops, `600` (10 min) is sufficient and reduces waste if
  the agent crashes or the user walks away
- Max allowed: `3600` (60 min) per job
- Max chain duration: 28 days of continuous reuse

---

## 5. Constraints & Limitations

- **No spot instances**: warm pools are incompatible with managed spot training
- **No heterogeneous clusters**: single instance type only
- **Volume size is locked**: cannot resize EBS between iterations
- **Quota is per-instance-type per-region**: switching instance types requires a
  separate quota grant and breaks the current pool
- **Pool is single-tenant**: only one job can match at a time; don't submit
  competing jobs from parallel agents against the same pool

---

## 6. Cleanup (Run When Done)

Release the warm pool immediately after the final iteration:

```python
import boto3
sm = boto3.client("sagemaker")
sm.update_training_job(
    TrainingJobName=last_job_name,
    ResourceConfig={"KeepAlivePeriodInSeconds": 0},
)
```

Or via CLI:
```bash
aws sagemaker update-training-job \
  --training-job-name <last-job-name> \
  --resource-config KeepAlivePeriodInSeconds=0
```

This is not optional. Warm pools bill at the full training rate ($2.80/hr for
ml.g6e.2xlarge) while idle. If you don't release, you pay for up to 30 min of
nothing after iteration ends.

---

## 7. Failure Taxonomy (What the Agent Should Recognize)

| Failure pattern | Likely cause | Fix approach |
|----------------|--------------|--------------|
| `ModuleNotFoundError` / `ImportError` | Missing or version-incompatible dependency | Bump pin in requirements.txt, resubmit |
| `CUDA out of memory` | Batch size or model too large for GPU | Reduce batch size, enable gradient checkpointing |
| `ResourceLimitExceeded` | Quota exhausted | Cannot continue — need quota increase or different instance |
| `InternalServerError` (job-level) | SageMaker infra issue | Pool is dead — next job cold-starts, retry same config |
| `AlgorithmError` (exit code != 0) | Bug in training script | Read traceback, patch script |
| Container timeout (no output) | Deadlock or infinite loop | Add timeout/watchdog, reduce scope |
