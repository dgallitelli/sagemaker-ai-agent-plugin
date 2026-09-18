# SageMaker SDK v3 — Pipeline Patterns

Advanced reference for SageMaker Pipelines. Use when the user wants to build a multi-step
ML workflow (preprocessing → training → evaluation → conditional registration).

> **V3 import change**: `sagemaker.workflow.*` no longer exists. Pipeline steps are in
> `sagemaker.mlops.workflow.*`, parameters/conditions/functions are in `sagemaker.core.workflow.*`.

---

## Session: `PipelineSession` vs `Session`

```python
from sagemaker.core.workflow.pipeline_context import PipelineSession
from sagemaker.core.helper.session_helper import Session

# Use PipelineSession when building pipeline steps — resources are NOT created yet
pipeline_session = PipelineSession()

# Use Session for actual execution (training jobs, endpoints)
session = Session()
```

Key difference: With `PipelineSession`, calls like `processor.run()` and `trainer.train()` return
pipeline step definitions — they do NOT execute immediately.

---

## Pipeline Parameters

```python
from sagemaker.core.workflow.parameters import ParameterString, ParameterInteger, ParameterFloat

# Declare parameters at the top — these become pipeline inputs
training_instance_type = ParameterString(
    name="TrainingInstanceType",
    default_value="ml.m5.xlarge",
)
model_approval_status = ParameterString(
    name="ModelApprovalStatus",
    default_value="PendingManualApproval",
)
input_data_uri = ParameterString(
    name="InputDataUri",
    default_value="s3://bucket/data/",
)
n_estimators = ParameterInteger(name="NEstimators", default_value=100)
```

---

## ProcessingStep

```python
from sagemaker.core.processing import ScriptProcessor, ProcessingInput, ProcessingOutput
from sagemaker.mlops.workflow.steps import ProcessingStep

processor = ScriptProcessor(
    image_uri=image_uri,
    role=role_arn,
    command=["python3"],
    instance_type="ml.m5.xlarge",
    instance_count=1,
    sagemaker_session=pipeline_session,
)

step_process = ProcessingStep(
    name="PreprocessData",
    processor=processor,
    inputs=[
        ProcessingInput(source=input_data_uri, destination="/opt/ml/processing/input"),
    ],
    outputs=[
        ProcessingOutput(output_name="train", source="/opt/ml/processing/train"),
        ProcessingOutput(output_name="validation", source="/opt/ml/processing/validation"),
    ],
    code="preprocessing.py",
)
```

---

## TrainingStep

```python
from sagemaker.train import ModelTrainer
from sagemaker.core.training.configs import Compute, SourceCode, OutputDataConfig
from sagemaker.mlops.workflow.steps import TrainingStep

trainer = ModelTrainer(
    training_image=image_uri,
    role=role_arn,
    source_code=SourceCode(source_dir="./training", entry_script="train.py"),
    compute=Compute(instance_type=training_instance_type, instance_count=1),
    output_data_config=OutputDataConfig(s3_output_path="s3://bucket/output/"),
    hyperparameters={"n-estimators": n_estimators},
    sagemaker_session=pipeline_session,
)

step_train = TrainingStep(
    name="TrainModel",
    step_args=trainer.train(
        input_data_config=[
            {
                "channel_name": "train",
                "data_source": {
                    "s3_data_source": {
                        # Reference output of ProcessingStep
                        "s3_uri": step_process.properties.ProcessingOutputConfig.Outputs[
                            "train"
                        ].S3Output.S3Uri,
                        "s3_data_type": "S3Prefix",
                    }
                },
            }
        ],
    ),
)
```

---

## ProcessingStep for Evaluation

```python
from sagemaker.core.processing import ScriptProcessor, ProcessingInput, ProcessingOutput
from sagemaker.core.workflow.properties import PropertyFile
from sagemaker.mlops.workflow.steps import ProcessingStep

evaluation_report = PropertyFile(
    name="EvaluationReport",
    output_name="evaluation",
    path="evaluation.json",
)

script_eval = ScriptProcessor(
    image_uri=image_uri,
    role=role_arn,
    command=["python3"],
    instance_type="ml.m5.xlarge",
    instance_count=1,
    sagemaker_session=pipeline_session,
)

step_eval = ProcessingStep(
    name="EvaluateModel",
    processor=script_eval,
    inputs=[
        ProcessingInput(
            source=step_train.properties.ModelArtifacts.S3ModelArtifacts,
            destination="/opt/ml/processing/model",
        ),
        ProcessingInput(
            source=step_process.properties.ProcessingOutputConfig.Outputs[
                "validation"
            ].S3Output.S3Uri,
            destination="/opt/ml/processing/test",
        ),
    ],
    outputs=[
        ProcessingOutput(output_name="evaluation", source="/opt/ml/processing/evaluation"),
    ],
    code="evaluate.py",
    property_files=[evaluation_report],
)
```

---

## ConditionStep (Register if Metric Passes)

```python
from sagemaker.core.workflow.conditions import ConditionGreaterThanOrEqualTo
from sagemaker.core.workflow.functions import JsonGet
from sagemaker.mlops.workflow.condition_step import ConditionStep

# Read metric from evaluation report
accuracy_condition = ConditionGreaterThanOrEqualTo(
    left=JsonGet(
        step_name=step_eval.name,
        property_file=evaluation_report,
        json_path="metrics.accuracy",
    ),
    right=0.85,  # threshold
)

step_cond = ConditionStep(
    name="CheckAccuracy",
    conditions=[accuracy_condition],
    if_steps=[step_register],   # defined below
    else_steps=[],
)
```

---

## RegisterModel Step

```python
from sagemaker.mlops.workflow.model_step import ModelStep
from sagemaker.core.resources import Model

model = Model(
    image_uri=image_uri,
    model_data=step_train.properties.ModelArtifacts.S3ModelArtifacts,
    role=role_arn,
    sagemaker_session=pipeline_session,
)

step_register = ModelStep(
    name="RegisterModel",
    step_args=model.register(
        content_types=["text/csv", "application/json"],
        response_types=["application/json"],
        inference_instances=["ml.m5.large"],
        transform_instances=["ml.m5.xlarge"],
        model_package_group_name="MyModelGroup",
        approval_status=model_approval_status,
    ),
)
```

---

## Full Pipeline Assembly

```python
from sagemaker.mlops.workflow.pipeline import Pipeline

pipeline = Pipeline(
    name="MyMLPipeline",
    parameters=[
        training_instance_type,
        model_approval_status,
        input_data_uri,
        n_estimators,
    ],
    steps=[step_process, step_train, step_eval, step_cond],
    sagemaker_session=pipeline_session,
)

# Create or update the pipeline definition in SageMaker
pipeline.upsert(role_arn=role_arn)

# Execute
execution = pipeline.start(
    parameters={
        "TrainingInstanceType": "ml.m5.2xlarge",
        "NEstimators": 200,
    }
)

execution.wait()
print(execution.describe())
```

---

## CacheConfig (skip re-running unchanged steps)

```python
from sagemaker.mlops.workflow import CacheConfig

cache_config = CacheConfig(enable_caching=True, expire_after="30d")

step_process = ProcessingStep(
    # ... other params ...
    cache_config=cache_config,
)
step_train = TrainingStep(
    # ... other params ...
    cache_config=cache_config,
)
```

---

## Cross-Step Data Flow via `.properties`

| Step type | Property to reference downstream |
|-----------|----------------------------------|
| TrainingStep | `step.properties.ModelArtifacts.S3ModelArtifacts` |
| ProcessingStep output | `step.properties.ProcessingOutputConfig.Outputs["name"].S3Output.S3Uri` |
| TransformStep | `step.properties.TransformOutput.S3OutputPath` |
| ModelStep | `step.properties.ModelPackageArn` |

These resolve at pipeline execution time — not at definition time.

---

## Evaluation Script Contract (`evaluate.py`)

The evaluation script must write a JSON file with metrics to the output directory:

```python
# evaluate.py — runs inside ProcessingStep container
import json
import os

# Load model and test data from /opt/ml/processing/model and /opt/ml/processing/test
# ... compute metrics ...

metrics = {
    "metrics": {
        "accuracy": 0.92,
        "auc": 0.95,
    }
}

output_dir = "/opt/ml/processing/evaluation"
os.makedirs(output_dir, exist_ok=True)
with open(os.path.join(output_dir, "evaluation.json"), "w") as f:
    json.dump(metrics, f)
```

The `JsonGet` function in ConditionStep reads from this file using `json_path="metrics.accuracy"`.

---

## V3 Import Quick Reference

| Class | V3 Import Path |
|-------|---------------|
| `Pipeline` | `sagemaker.mlops.workflow.pipeline` |
| `PipelineSession` | `sagemaker.core.workflow.pipeline_context` |
| `TrainingStep`, `ProcessingStep` | `sagemaker.mlops.workflow.steps` |
| `ConditionStep` | `sagemaker.mlops.workflow.condition_step` |
| `ModelStep` | `sagemaker.mlops.workflow.model_step` |
| `CacheConfig` | `sagemaker.mlops.workflow` |
| `ParameterString`, `ParameterInteger`, `ParameterFloat` | `sagemaker.core.workflow.parameters` |
| `ConditionGreaterThanOrEqualTo`, etc. | `sagemaker.core.workflow.conditions` |
| `JsonGet` | `sagemaker.core.workflow.functions` |
| `PropertyFile` | `sagemaker.core.workflow.properties` |
| `ProcessingInput`, `ProcessingOutput` | `sagemaker.core.processing` |
| `ScriptProcessor` | `sagemaker.core.processing` |
| `Model` | `sagemaker.core.resources` |
