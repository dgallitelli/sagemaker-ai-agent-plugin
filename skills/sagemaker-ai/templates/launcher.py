"""
SageMaker Python SDK v3 — Canonical Training Job Launcher

Usage:
    python launcher.py \
        --role arn:aws:iam::123456789012:role/SageMakerRole \
        --s3-input s3://my-bucket/data/train/ \
        --s3-output s3://my-bucket/output/ \
        [--instance-type ml.m5.xlarge] \
        [--region us-east-1] \
        [--framework xgboost]
"""
import argparse
import boto3

from sagemaker.train import ModelTrainer
from sagemaker.core.helper.session_helper import Session
from sagemaker.core import image_uris
from sagemaker.core.training.configs import (
    Compute,
    SourceCode,
    OutputDataConfig,
    StoppingCondition,
)


# ---------------------------------------------------------------------------
# IAM role discovery (works outside SageMaker Studio)
# ---------------------------------------------------------------------------
def get_role(role_arn=None):
    """Return a role ARN. If role_arn is provided, use it directly.
    Otherwise discover the first IAM role with 'SageMaker' in the name."""
    if role_arn:
        return role_arn
    iam = boto3.client("iam")
    paginator = iam.get_paginator("list_roles")
    for page in paginator.paginate():
        for role in page["Roles"]:
            name = role["RoleName"]
            if "SageMaker" in name or "sagemaker" in name:
                print(f"Discovered role: {role['Arn']}")
                return role["Arn"]
    raise ValueError(
        "No SageMaker IAM role found automatically. Pass --role explicitly."
    )


# ---------------------------------------------------------------------------
# Image URI lookup per framework
# ---------------------------------------------------------------------------
FRAMEWORK_VERSIONS = {
    "xgboost": {"version": "1.7-1"},
    "sklearn": {"version": "1.2-1"},
    "pytorch": {"version": "2.1", "py_version": "py310"},
}


def get_image_uri(framework, region, instance_type):
    cfg = FRAMEWORK_VERSIONS.get(framework)
    if cfg is None:
        raise ValueError(f"Unknown framework '{framework}'. Choose: xgboost, sklearn, pytorch")

    kwargs = dict(framework=framework, region=region, version=cfg["version"])
    if "py_version" in cfg:
        kwargs["py_version"] = cfg["py_version"]
        kwargs["instance_type"] = instance_type
        kwargs["image_scope"] = "training"
    return image_uris.retrieve(**kwargs)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Launch a SageMaker training job")
    parser.add_argument("--role", default=None, help="IAM role ARN (auto-discovered if omitted)")
    parser.add_argument("--s3-input", required=True, help="S3 URI prefix for training data")
    parser.add_argument("--s3-output", required=True, help="S3 URI prefix for model artifacts")
    parser.add_argument("--instance-type", default="ml.m5.xlarge", help="SageMaker instance type")
    parser.add_argument("--region", default=None, help="AWS region (uses boto3 default if omitted)")
    parser.add_argument("--framework", default="xgboost", choices=["xgboost", "sklearn", "pytorch"])
    parser.add_argument("--source-dir", default="./training", help="Local directory with train.py")
    parser.add_argument("--entry-script", default="train.py", help="Training script filename")
    parser.add_argument("--job-name", default=None, help="Base name for the training job")
    args = parser.parse_args()

    region = args.region or boto3.session.Session().region_name
    role_arn = get_role(args.role)
    image_uri = get_image_uri(args.framework, region, args.instance_type)

    print(f"Framework  : {args.framework}")
    print(f"Image URI  : {image_uri}")
    print(f"Instance   : {args.instance_type}")
    print(f"S3 input   : {args.s3_input}")
    print(f"S3 output  : {args.s3_output}")
    print(f"Role       : {role_arn}")

    # Hyperparameters — framework-specific defaults, update for your model
    default_hps = {
        "xgboost": {"n-estimators": 100, "max-depth": 5, "learning-rate": 0.1, "objective": "binary:logistic"},
        "sklearn": {"n-estimators": 100, "max-depth": "None", "random-state": 42},
        "pytorch": {"epochs": 10, "batch-size": 64, "lr": 0.001, "hidden-dim": 128, "num-layers": 2},
    }
    hyperparameters = default_hps.get(args.framework, {})

    trainer = ModelTrainer(
        training_image=image_uri,
        role=role_arn,
        source_code=SourceCode(
            source_dir=args.source_dir,
            entry_script=args.entry_script,
            requirements="requirements.txt",
        ),
        compute=Compute(
            instance_type=args.instance_type,
            instance_count=1,
            volume_size_in_gb=30,
            keep_alive_period_in_seconds=0,
        ),
        output_data_config=OutputDataConfig(
            s3_output_path=args.s3_output,
        ),
        hyperparameters=hyperparameters,
        base_job_name=args.job_name or f"training-{args.framework}",
        stopping_condition=StoppingCondition(
            max_runtime_in_seconds=3600,
        ),
        sagemaker_session=Session(),
    )

    trainer.train(
        input_data_config=[
            {
                "channel_name": "train",
                "data_source": {
                    "s3_data_source": {
                        "s3_uri": args.s3_input,
                        "s3_data_type": "S3Prefix",
                    }
                },
            },
            # Uncomment to add a validation channel:
            # {
            #     "channel_name": "validation",
            #     "data_source": {
            #         "s3_data_source": {
            #             "s3_uri": "s3://bucket/data/validation/",
            #             "s3_data_type": "S3Prefix",
            #         }
            #     },
            # },
        ],
        wait=True,   # set wait=False for async (returns immediately, check console)
        logs=True,   # boolean — NOT the string 'All'
    )

    job_name = trainer.latest_training_job.name
    print(f"\nTraining job complete: {job_name}")
    print(
        f"Console: https://{region}.console.aws.amazon.com/sagemaker/home"
        f"?region={region}#/jobs/{job_name}"
    )


if __name__ == "__main__":
    main()
