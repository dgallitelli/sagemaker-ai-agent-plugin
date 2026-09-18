<div align="center">

# SageMaker AI Agent Plugin

One portable package for building, training, deploying, monitoring, and
operating machine-learning workloads on Amazon SageMaker AI.

[![GitHub stars](https://img.shields.io/github/stars/dgallitelli/sagemaker-ai-agent-plugin?style=for-the-badge&logo=github)](https://github.com/dgallitelli/sagemaker-ai-agent-plugin/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Agent Plugin](https://img.shields.io/badge/Agent_Plugin-1.1.0-7B61FF?style=for-the-badge)](plugin.json)

**Codex · Kiro · Claude Code**

</div>

## What it covers

| Area | Capabilities |
|---|---|
| SDK and workflows | SageMaker Python SDK v3, v2 migration, Pipelines, processing, HPO |
| Training | Classical ML, SFT, LoRA, QLoRA, DPO, CPT, RLVR, RLAIF, Trainium |
| Inference | Real-time, batch, JumpStart, DJL LMI, vLLM, HyperPod |
| Operations | HyperPod with EKS or Slurm, Model Monitor, AutoGluon |
| Iteration | Managed warm pools for repeated training and experimentation |

The package uses one canonical skill under `skills/sagemaker-ai/`. IDE-specific
manifests only handle discovery and installation.

## Install

### Codex

Add this repository as a plugin marketplace:

```bash
codex plugin marketplace add dgallitelli/sagemaker-ai-agent-plugin
codex plugin add sagemaker-ai@dgallitelli-sagemaker-ai
```

Restart Codex to load the plugin. Alternatively, run `/plugins`, open the
`SageMaker AI Plugins` marketplace, and install `sagemaker-ai` interactively.

The Codex package includes the SageMaker skill and the optional official AWS
Labs SageMaker AI MCP server configuration.

### Claude Code

Add the marketplace and install the plugin:

```bash
claude plugin marketplace add dgallitelli/sagemaker-ai-agent-plugin
claude plugin install sagemaker-ai@dgallitelli-sagemaker-ai
```

Restart Claude Code after installation. You can inspect or update it later with:

```bash
claude plugin list
claude plugin update sagemaker-ai@dgallitelli-sagemaker-ai
```

### Kiro

1. Open the **Powers** panel in Kiro.
2. Select **Add Custom Power**.
3. Choose **Import power from GitHub**.
4. Enter:

   ```text
   https://github.com/dgallitelli/sagemaker-ai-agent-plugin
   ```

5. Install the Power, then enable and trust it when prompted.

For a skill-only installation, import this folder instead:

```text
https://github.com/dgallitelli/sagemaker-ai-agent-plugin/tree/main/skills/sagemaker-ai
```

### Manual skill-only installation

Clients that support Agent Skills can link the canonical skill directly:

```bash
git clone https://github.com/dgallitelli/sagemaker-ai-agent-plugin.git
cd sagemaker-ai-agent-plugin
```

Choose the destination for your client:

```bash
# Codex
mkdir -p ~/.codex/skills
ln -s "$PWD/skills/sagemaker-ai" ~/.codex/skills/sagemaker-ai

# Claude Code
mkdir -p ~/.claude/skills
ln -s "$PWD/skills/sagemaker-ai" ~/.claude/skills/sagemaker-ai

# Kiro
mkdir -p ~/.kiro/skills
ln -s "$PWD/skills/sagemaker-ai" ~/.kiro/skills/sagemaker-ai
```

## Package layout

```text
.
├── plugin.json                       # Agent Plugins / Kiro
├── mcp.json                          # Agent Plugins MCP definition
├── .mcp.json                         # Shared Codex / Claude MCP definition
├── .agents/plugins/marketplace.json  # Codex marketplace
├── .codex-plugin/                    # Codex manifest
├── .claude-plugin/                   # Claude Code manifest and marketplace
└── skills/sagemaker-ai/
    ├── SKILL.md                      # Routing and operating rules
    ├── references/                   # Detailed guidance
    ├── scripts/                      # Reusable utilities
    ├── templates/                    # Training and inference templates
    └── assets/                       # HyperPod examples
```

## Optional AWS MCP server

The plugin configures the official AWS Labs package:

```text
awslabs.sagemaker-ai-mcp-server@latest
```

It is intentionally configured without write or sensitive-data flags. The
server currently focuses on SageMaker HyperPod operations; the skill uses the
AWS CLI, boto3, and SageMaker Python SDK v3 for other workflows.

The skill remains usable when the MCP server is unavailable.

## Requirements

- Python 3.10–3.13 for SageMaker Python SDK v3 workflows
- AWS CLI with configured credentials
- `uv`/`uvx` when using the optional MCP server

## Consolidated projects

This plugin brings together capabilities previously spread across:

- `claude-code-skill-for-sagemaker-ai`
- `sagemaker-python-sdk-skill`
- `aws-hyperpod-skill`
- `kiro-power-for-sagemaker-ai`
- the original LLM-training skill in this repository

It does not include or depend on `dgallitelli/sagemaker-ai-mcp-server`.

The focused
[`sagemaker-warm-pool-researcher`](https://github.com/dgallitelli/sagemaker-warm-pool-researcher)
remains independently installable, while its capabilities are also available
inside this plugin.

## License

MIT. HyperPod-derived material retains its Apache-2.0 terms; see
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
