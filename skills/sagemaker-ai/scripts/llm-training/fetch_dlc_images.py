#!/usr/bin/env python3
"""Fetch current SageMaker Deep Learning Container images.

Usage:
    python scripts/llm-training/fetch_dlc_images.py [--framework pytorch] [--region us-east-1]

IMPORTANT: For the most up-to-date container images, always reference:
    https://aws.github.io/deep-learning-containers/reference/available_images/

This script queries ECR for available images but may have stale fallback values.
When in doubt, use WebFetch to query the official DLC documentation page.
"""
import argparse
import json
import subprocess
import sys
from typing import Optional


def get_pytorch_training_images(region: str = "us-east-1") -> list[dict]:
    """Fetch available PyTorch training DLC images from ECR."""
    account_id = "763104351884"  # AWS DLC account
    repo = "pytorch-training"

    try:
        # List available tags from ECR public gallery
        result = subprocess.run(
            [
                "aws", "ecr", "describe-images",
                "--registry-id", account_id,
                "--repository-name", repo,
                "--region", region,
                "--query", "imageDetails[?contains(imageTags[0], 'gpu') && contains(imageTags[0], 'sagemaker')].imageTags[0]",
                "--output", "json"
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            tags = json.loads(result.stdout)
            # Filter for recent PyTorch 2.x versions
            pytorch2_tags = [t for t in tags if t and t.startswith("2.")]
            pytorch2_tags.sort(reverse=True)

            images = []
            for tag in pytorch2_tags[:5]:  # Top 5 recent versions
                images.append({
                    "tag": tag,
                    "uri": f"{account_id}.dkr.ecr.{region}.amazonaws.com/{repo}:{tag}"
                })
            return images
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass

    # Fallback: return known stable versions (may be stale!)
    # ALWAYS verify against: https://aws.github.io/deep-learning-containers/reference/available_images/
    return [
        {
            "tag": "2.5.1-gpu-py311-cu124-ubuntu22.04-sagemaker",
            "uri": f"{account_id}.dkr.ecr.{region}.amazonaws.com/{repo}:2.5.1-gpu-py311-cu124-ubuntu22.04-sagemaker",
            "note": "⚠️ FALLBACK - verify at https://aws.github.io/deep-learning-containers/reference/available_images/"
        }
    ]


def get_neuron_training_images(region: str = "us-east-1") -> list[dict]:
    """Fetch available Neuron/Trainium training images."""
    account_id = "763104351884"
    repo = "pytorch-training-neuronx"

    try:
        result = subprocess.run(
            [
                "aws", "ecr", "describe-images",
                "--registry-id", account_id,
                "--repository-name", repo,
                "--region", region,
                "--query", "imageDetails[?imageTags].imageTags[0]",
                "--output", "json"
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            tags = json.loads(result.stdout)
            tags = [t for t in tags if t]
            tags.sort(reverse=True)

            images = []
            for tag in tags[:3]:
                images.append({
                    "tag": tag,
                    "uri": f"{account_id}.dkr.ecr.{region}.amazonaws.com/{repo}:{tag}"
                })
            return images
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass

    # Fallback: return known stable versions (may be stale!)
    # ALWAYS verify against: https://aws.github.io/deep-learning-containers/reference/available_images/
    return [
        {
            "tag": "2.1.2-neuronx-py310-sdk2.20.2-ubuntu20.04",
            "uri": f"{account_id}.dkr.ecr.{region}.amazonaws.com/{repo}:2.1.2-neuronx-py310-sdk2.20.2-ubuntu20.04",
            "note": "⚠️ FALLBACK - verify at https://aws.github.io/deep-learning-containers/reference/available_images/"
        }
    ]


def main():
    parser = argparse.ArgumentParser(description="Fetch SageMaker DLC images")
    parser.add_argument("--framework", default="pytorch", choices=["pytorch", "neuron"])
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.framework == "pytorch":
        images = get_pytorch_training_images(args.region)
    else:
        images = get_neuron_training_images(args.region)

    if args.json:
        print(json.dumps(images, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"SageMaker {args.framework.upper()} Training Images ({args.region})")
        print(f"{'='*60}\n")

        for img in images:
            print(f"Tag: {img['tag']}")
            print(f"URI: {img['uri']}")
            if "note" in img:
                print(f"⚠️  {img['note']}")
            print()


if __name__ == "__main__":
    main()
