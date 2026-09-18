# SageMaker AI Agent Plugin

A portable Agent Plugin for building, training, deploying, monitoring, and operating machine-learning workloads on Amazon SageMaker AI.

The repository contains one canonical Agent Skill that can be consumed by clients supporting the Agent Skills or Agent Plugins standards, including Codex, Kiro, and Claude Code.

## Package layout

```text
.
├── plugin.json
├── mcp.json
├── .claude-plugin/
│   └── plugin.json
└── skills/
    └── sagemaker-ai/
        ├── SKILL.md
        ├── references/
        ├── scripts/
        ├── templates/
        └── assets/
```

The files under `skills/sagemaker-ai/` are the only maintained knowledge source. Client-specific manifests contain packaging metadata only.

## Consolidated sources

This package consolidates the original LLM-training skill in this repository
with the overlapping capabilities in:

- `claude-code-skill-for-sagemaker-ai`
- `sagemaker-python-sdk-skill`
- `aws-hyperpod-skill`
- `kiro-power-for-sagemaker-ai`

It does not include or depend on `dgallitelli/sagemaker-ai-mcp-server`.

## Capabilities

- SageMaker Python SDK v3 patterns and v2-to-v3 migration guidance
- Classical ML and LLM training jobs
- SFT, LoRA, QLoRA, DPO, CPT, RLVR, and RLAIF workflows
- Real-time, batch, LLM, and HyperPod inference
- HyperPod provisioning and operations with EKS or Slurm
- SageMaker Model Monitor
- AutoGluon and SageMaker Pipelines
- Iterative training with managed warm pools

The warm-pool capability is included in this plugin, while the focused [`sagemaker-warm-pool-researcher`](https://github.com/dgallitelli/sagemaker-warm-pool-researcher) skill remains independently installable.

## Installation

Install the repository root when the client supports Agent Plugins. Clients that support Agent Skills directly can install or link `skills/sagemaker-ai/` into their user or project skill directory.

The `.claude-plugin/plugin.json` manifest is a thin compatibility adapter for Claude Code. It references the same root `skills/` directory and does not duplicate the skill.

## Official AWS MCP server

The optional `mcp.json` configuration uses the official AWS Labs package:

```text
awslabs.sagemaker-ai-mcp-server@latest
```

It is configured without write or sensitive-data flags. The server currently focuses on SageMaker HyperPod operations. Other SageMaker work uses the AWS CLI, boto3, and SageMaker Python SDK v3 guidance in the skill.

The MCP server requires `uv`/`uvx` and configured AWS credentials. The skill remains usable when the MCP server is unavailable.

## Requirements

- Python 3.10–3.13 for SageMaker Python SDK v3 workflows
- AWS CLI with appropriate credentials
- `uvx` only when using the optional AWS Labs MCP server

## License

MIT. HyperPod-derived material retains its Apache-2.0 terms; see
`THIRD_PARTY_NOTICES.md`.
