# Neuron Compilation Test

Test whether a HuggingFace model can compile on AWS Trainium/Neuron before committing to a full training job.

## When to Use

- Model architecture is **not listed** on the [supported architectures page](https://huggingface.co/docs/optimum-neuron/en/supported_architectures)
- Model uses custom architecture with `trust_remote_code=True`
- User wants to verify Neuron compatibility before training

## How It Works

1. Launch a small Trainium EC2 instance (trn1.2xlarge, ~$1.34/hr)
2. SSH in and run a compilation test script
3. Test loads the model and runs a forward pass on Neuron
4. Results indicate compatibility (or specific failure reason)
5. Terminate instance when done

## Common Failure Modes

| Error | Meaning | Action |
|-------|---------|--------|
| `model_type not recognized` | Custom architecture | Ensure `trust_remote_code=True`, check transformers version |
| `int64 matmul not supported` | Model uses unsupported ops | **Incompatible** - use GPU instead |
| `tokenizers` error | Tokenizer format too new | Upgrade transformers in container |
| Forward pass timeout | Model too large or compilation hanging | Try larger instance or simplify model |

## Deployment Steps

### Step 1: SSH Key

Ask user:
```
Do you have an existing EC2 key pair for SSH access?
- Yes, use existing: [key pair name]
- No, create a new one
```

If creating new:
```bash
aws ec2 create-key-pair \
  --key-name neuron-compile-test-key \
  --query 'KeyMaterial' \
  --region <region> \
  --output text > neuron-compile-test-key.pem
chmod 400 neuron-compile-test-key.pem
```

### Step 2: Deploy Stack

```bash
aws cloudformation create-stack \
  --stack-name neuron-compile-test \
  --template-body file://templates/trainium/cfn-neuron-compile-test.yaml \
  --parameters \
    ParameterKey=KeyPairName,ParameterValue=<key-name> \
    ParameterKey=AllowedSSHCidr,ParameterValue=<user-ip>/32 \
  --region <region>

# Wait for completion
aws cloudformation wait stack-create-complete --stack-name neuron-compile-test --region <region>

# Get outputs
aws cloudformation describe-stacks --stack-name neuron-compile-test --region <region> \
  --query 'Stacks[0].Outputs'
```

### Step 3: Run Test (One-Liner)

```bash
# Get instance IP
IP=$(aws cloudformation describe-stacks --stack-name neuron-compile-test --region <region> \
  --query 'Stacks[0].Outputs[?OutputKey==`PublicIP`].OutputValue' --output text)

# SSH + activate + test (one command)
ssh -i <key>.pem ubuntu@$IP "source /opt/aws_neuronx_venv_pytorch_2_9_nxd_training/bin/activate && \
  pip install -q 'transformers>=5.0' && \
  cd ~/neuron-test && \
  MODEL_ID='<model-id>' python test_neuron_compile.py"
```

### Step 4: Interpret Results

**SUCCESS:**
```
RESULT: Neuron compilation test PASSED
```
→ Model is compatible with Trainium. Proceed with training.

**FAILURE - Unsupported ops:**
```
[NCC_EUMT001] matmul cannot be performed with int64 operands
```
→ Model uses operations Neuron doesn't support. **Use GPU instead.**

**FAILURE - Architecture:**
```
model_type 'xyz' not recognized
```
→ Check transformers version, ensure `trust_remote_code=True`.

### Step 5: Cleanup

```bash
# Delete stack (terminates instance)
aws cloudformation delete-stack --stack-name neuron-compile-test --region <region>

# Optionally delete key pair
aws ec2 delete-key-pair --key-name neuron-compile-test-key --region <region>
```

## Cost

- **trn1.2xlarge**: ~$1.34/hour
- Typical test: 10-15 minutes = **~$0.25-0.35**
- Much cheaper than failed SageMaker jobs

## Test Script Location

The test script is automatically deployed to `~/neuron-test/test_neuron_compile.py` on the instance.

To test multiple models:
```bash
MODEL_ID='meta-llama/Llama-3.1-8B' python test_neuron_compile.py
MODEL_ID='mistralai/Mistral-7B-v0.1' python test_neuron_compile.py
MODEL_ID='custom/my-model' python test_neuron_compile.py
```
