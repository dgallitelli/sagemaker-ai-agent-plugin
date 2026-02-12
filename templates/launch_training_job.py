#!/usr/bin/env python3
"""
Launch SageMaker Training Job for LLM fine-tuning with LoRA.

This script uses the SageMaker Python SDK v3 to launch a training job
with QLoRA (4-bit quantization + LoRA) for memory-efficient fine-tuning.

Note: This script does not require a GPU to run. It launches training jobs
on remote SageMaker instances - your local environment only needs the
SageMaker SDK and AWS credentials.

Requirements:
    - Python ≤3.13 (SDK v3 not compatible with 3.14+)
    - pip install sagemaker boto3

Usage:
    python launch_training_job.py              # Launch training job
    python launch_training_job.py --deploy     # Deploy completed model to endpoint
"""
import argparse
import os
import boto3
from sagemaker.train import ModelTrainer, Session, get_execution_role
from sagemaker.core import image_uris
from sagemaker.core.training.configs import (
    Compute,
    SourceCode,
    OutputDataConfig,
    CheckpointConfig,
    StoppingCondition,
)


def main():
    # Initialize SageMaker session
    sess = Session()
    region = sess.boto_region_name
    default_bucket = sess.default_bucket()

    # ==========================================================================
    # CONFIGURATION - Customize these for your training job
    # ==========================================================================

    # IMPORTANT: Use a SageMaker execution role, not your SSO/IAM user role
    # You can find existing roles in the IAM console under Roles > search "SageMaker"
    role = "<YOUR_SAGEMAKER_EXECUTION_ROLE_ARN>"

    # S3 paths
    train_data = "s3://<YOUR_BUCKET>/datasets/<YOUR_DATASET>/"
    output_path = f"s3://{default_bucket}/training-outputs"

    # Job configuration
    base_job_name = "lora-sft"
    job_name = f"{base_job_name}-qlora"

    # ==========================================================================
    # Training environment variables (passed to training script)
    # ==========================================================================
    training_env = {
        # Model to fine-tune (any HuggingFace model ID)
        "MODEL_ID": "meta-llama/Llama-3.1-8B-Instruct",

        # Training configuration
        "NUM_EPOCHS": "3",
        "BATCH_SIZE": "2",
        "GRADIENT_ACCUMULATION": "4",  # Effective batch = BATCH_SIZE * GRADIENT_ACCUMULATION
        "LEARNING_RATE": "2e-4",
        "MAX_SEQ_LENGTH": "2048",

        # LoRA configuration
        "LORA_R": "16",      # LoRA rank (higher = more capacity, more memory)
        "LORA_ALPHA": "32",  # LoRA alpha (typically 2x rank)

        # Training data channel
        "SM_CHANNEL_TRAIN": "/opt/ml/input/data/train",

        # HuggingFace Hub token (for gated models like Llama)
        "HUGGING_FACE_HUB_TOKEN": "",
    }

    # ==========================================================================
    # Get PyTorch training container image
    # ==========================================================================
    # See available images: https://aws.github.io/deep-learning-containers/reference/available_images/
    pytorch_image_uri = image_uris.retrieve(
        framework="pytorch",
        region=region,
        version="2.5.1",
        py_version="py311",
        image_scope="training",
        instance_type="ml.g5.12xlarge",
    )
    print(f"Using container: {pytorch_image_uri}")

    # ==========================================================================
    # Configure source code
    # ==========================================================================
    source_code = SourceCode(
        source_dir="./scripts",
        command="pip install -r requirements.txt && python train_lora.py",
    )

    # ==========================================================================
    # Configure compute resources
    # ==========================================================================
    compute_config = Compute(
        instance_type="ml.g5.12xlarge",      # 4x A10G GPUs, 96GB total VRAM
        instance_count=1,                     # Use 2+ for multi-node training
        keep_alive_period_in_seconds=1800,   # Warm pool for faster iterations
        volume_size_in_gb=300,               # Storage for model downloads
    )

    # ==========================================================================
    # Create ModelTrainer
    # ==========================================================================
    model_trainer = ModelTrainer(
        training_image=pytorch_image_uri,
        source_code=source_code,
        base_job_name=base_job_name,
        compute=compute_config,
        role=role,
        environment=training_env,

        # Training data input
        input_data_config=[
            {
                "channel_name": "train",
                "data_source": {
                    "s3_data_source": {
                        "s3_uri": train_data,
                        "s3_data_type": "S3Prefix",
                    }
                },
            }
        ],

        # Output configuration
        output_data_config=OutputDataConfig(
            s3_output_path=output_path,
        ),

        # Checkpointing
        checkpoint_config=CheckpointConfig(
            s3_uri=os.path.join(output_path, job_name, "checkpoints"),
            local_path="/opt/ml/checkpoints",
        ),

        # Timeout
        stopping_condition=StoppingCondition(
            max_runtime_in_seconds=86400,  # 24 hours max
        ),
    )

    # ==========================================================================
    # Start training
    # ==========================================================================
    print("Starting SageMaker Training Job...")
    model_trainer.train(wait=False)  # Set wait=True to block until completion

    print(f"\nTraining job started!")
    print(f"Monitor at: https://console.aws.amazon.com/sagemaker/home?region={region}#/jobs")


def deploy(job_name: str = None):
    """Deploy a completed training job to a SageMaker endpoint."""
    from sagemaker.huggingface import HuggingFaceModel

    sess = Session()
    region = sess.boto_region_name
    sm_client = boto3.client("sagemaker")

    # IMPORTANT: Use a SageMaker execution role, not your SSO/IAM user role
    role = "<YOUR_SAGEMAKER_EXECUTION_ROLE_ARN>"

    base_job_name = "lora-sft"

    # Find the latest completed training job if not specified
    if job_name is None:
        response = sm_client.list_training_jobs(
            NameContains=base_job_name,
            StatusEquals="Completed",
            MaxResults=1,
            SortBy="CreationTime",
            SortOrder="Descending",
        )
        if not response["TrainingJobSummaries"]:
            print("No completed training jobs found.")
            return
        job_name = response["TrainingJobSummaries"][0]["TrainingJobName"]

    # Get model artifacts location
    response = sm_client.describe_training_job(TrainingJobName=job_name)
    if response["TrainingJobStatus"] != "Completed":
        print(f"Training job {job_name} is not completed (status: {response['TrainingJobStatus']})")
        return

    model_s3_uri = response["ModelArtifacts"]["S3ModelArtifacts"]
    print(f"Model artifacts: {model_s3_uri}")

    # Get inference container
    inference_image_uri = image_uris.retrieve(
        framework="huggingface-llm",
        region=region,
        version="2.5.1",
        image_scope="inference",
        instance_type="ml.g5.2xlarge",
    )

    # Create SageMaker Model
    huggingface_model = HuggingFaceModel(
        model_data=model_s3_uri,
        role=role,
        image_uri=inference_image_uri,
        env={
            "HF_MODEL_ID": "/opt/ml/model",
            "SM_NUM_GPUS": "1",
        },
    )

    # Deploy to endpoint
    # Use ml.g5.2xlarge (1x A10G, 24GB) for 8B models with LoRA adapters
    endpoint_name = f"{base_job_name}-endpoint"
    print(f"Deploying to endpoint: {endpoint_name}")

    predictor = huggingface_model.deploy(
        initial_instance_count=1,
        instance_type="ml.g5.2xlarge",
        endpoint_name=endpoint_name,
    )

    print(f"\nEndpoint deployed: {predictor.endpoint_name}")
    print(f"Test with:")
    print(f'  predictor.predict({{"inputs": "What is machine learning?"}})')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Launch SageMaker Training Job or Deploy Model")
    parser.add_argument("--deploy", action="store_true", help="Deploy completed model to endpoint")
    parser.add_argument("--job-name", type=str, help="Training job name (for deployment)")
    args = parser.parse_args()

    if args.deploy:
        deploy(args.job_name)
    else:
        main()
