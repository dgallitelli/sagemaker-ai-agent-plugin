# EKS Troubleshooting Guide

This guide covers common issues and solutions for HyperPod with EKS orchestration.

## Diagnostic Commands

### Cluster Health Check

```bash
# Check all nodes
kubectl get nodes -o wide

# Check node conditions
kubectl describe nodes | grep -A10 "Conditions:"

# Check system pods
kubectl get pods -n kube-system

# Check HyperPod components
kubectl get pods -n hyperpod-system
```

### Job Diagnostics

```bash
# Check PyTorchJob status
kubectl describe pytorchjob <job-name>

# Check worker pods
kubectl get pods -l pytorch-job-name=<job-name>

# Get pod events
kubectl describe pod <pod-name>

# View pod logs
kubectl logs <pod-name> --tail=100

# View previous container logs (after crash)
kubectl logs <pod-name> --previous
```

## Node Issues

### Nodes Not Ready

**Symptom**: Nodes show `NotReady` status

```bash
kubectl get nodes
# NAME           STATUS     ROLES    AGE   VERSION
# ip-10-0-1-10   NotReady   <none>   5m    v1.29.0
```

**Diagnosis**:
```bash
# Check node conditions
kubectl describe node ip-10-0-1-10 | grep -A20 "Conditions:"

# Check kubelet logs (via SSM)
aws ssm start-session --target i-xxxxx
journalctl -u kubelet -n 100
```

**Solutions**:

| Condition | Solution |
|-----------|----------|
| NetworkUnavailable | Check VPC CNI plugin, security groups |
| MemoryPressure | Increase node memory or reduce workload |
| DiskPressure | Clean up disk, increase EBS volume |
| PIDPressure | Reduce container count |

### GPUs Not Detected

**Symptom**: GPU resources not showing

```bash
kubectl describe node ip-10-0-1-10 | grep -A5 "Capacity:"
# nvidia.com/gpu: 0  # Should be 8
```

**Diagnosis**:
```bash
# Check NVIDIA device plugin
kubectl get pods -n kube-system | grep nvidia
kubectl logs -n kube-system nvidia-device-plugin-xxxxx

# Check on node
aws ssm start-session --target i-xxxxx
nvidia-smi
```

**Solutions**:

1. **Reinstall device plugin**:
```bash
kubectl delete daemonset nvidia-device-plugin-daemonset -n kube-system
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.0/nvidia-device-plugin.yml
```

2. **Check driver installation**:
```bash
# On node
nvidia-smi
# If fails, drivers not installed correctly
# Check lifecycle script logs
```

### EFA Not Available

**Symptom**: EFA resources missing

```bash
kubectl describe node | grep efa
# vpc.amazonaws.com/efa: 0  # Should be >0
```

**Diagnosis**:
```bash
# Check EFA device plugin
kubectl get pods -n kube-system | grep efa
kubectl logs -n kube-system aws-efa-k8s-device-plugin-xxxxx

# Check on node
aws ssm start-session --target i-xxxxx
fi_info -p efa
```

**Solutions**:

1. **Verify instance type supports EFA**
2. **Check security group allows all traffic from self**
3. **Reinstall EFA device plugin**

## Pod Issues

### Pods Pending

**Symptom**: Pods stuck in Pending state

```bash
kubectl get pods
# NAME                    STATUS    AGE
# training-worker-0       Pending   10m
```

**Diagnosis**:
```bash
kubectl describe pod training-worker-0
# Look for Events section
```

**Common Causes and Solutions**:

| Event Message | Solution |
|---------------|----------|
| "Insufficient nvidia.com/gpu" | Not enough GPUs available, scale nodes or reduce request |
| "Insufficient memory" | Reduce memory request or add nodes |
| "0/4 nodes are available" | Check node selector, tolerations |
| "persistentvolumeclaim not found" | Create required PVC |

### Pod CrashLoopBackOff

**Symptom**: Pod repeatedly crashing

```bash
kubectl get pods
# NAME              STATUS             RESTARTS   AGE
# training-0       CrashLoopBackOff   5          10m
```

**Diagnosis**:
```bash
# Check current logs
kubectl logs training-0

# Check previous container logs
kubectl logs training-0 --previous

# Check exit code
kubectl describe pod training-0 | grep -A5 "Last State:"
```

**Common Exit Codes**:

| Exit Code | Meaning | Solution |
|-----------|---------|----------|
| 1 | Application error | Check application logs |
| 137 | OOM killed | Increase memory limit |
| 139 | Segmentation fault | Check CUDA/driver compatibility |
| 255 | Unknown error | Check full logs |

### OOM Killed

**Symptom**: Container killed due to memory

```bash
kubectl describe pod training-0 | grep OOMKilled
# Reason: OOMKilled
```

**Solutions**:

1. **Increase memory limit**:
```yaml
resources:
  limits:
    memory: 1500Gi  # Increase from current
```

2. **Increase shared memory**:
```yaml
volumes:
  - name: dshm
    emptyDir:
      medium: Memory
      sizeLimit: 200Gi  # Increase for large batches
```

3. **Reduce batch size in training script**

## Networking Issues

### NCCL Timeout

**Symptom**: Training hangs or times out during communication

```
[E] NCCL WARN Cuda failure 'out of memory'
[E] NCCL WARN Call to cuMemAlloc failed
NCCL TIMEOUT
```

**Diagnosis**:
```bash
# Check NCCL debug output
kubectl logs training-worker-0 | grep NCCL

# Verify network connectivity
kubectl exec training-worker-0 -- ping <worker-1-ip>
```

**Solutions**:

1. **Increase NCCL timeout**:
```yaml
env:
  - name: NCCL_TIMEOUT
    value: "3600"
```

2. **Fix NCCL socket interface**:
```yaml
env:
  - name: NCCL_SOCKET_IFNAME
    value: "eth0"
  - name: NCCL_IB_DISABLE
    value: "1"
```

3. **Use EFA for communication**:
```yaml
env:
  - name: FI_PROVIDER
    value: "efa"
  - name: FI_EFA_USE_DEVICE_RDMA
    value: "1"
```

### DNS Resolution Failures

**Symptom**: Cannot resolve service names

```
getaddrinfo: Name or service not known
```

**Diagnosis**:
```bash
# Check CoreDNS
kubectl get pods -n kube-system | grep coredns
kubectl logs -n kube-system coredns-xxxxx
```

**Solutions**:

1. **Restart CoreDNS**:
```bash
kubectl rollout restart deployment coredns -n kube-system
```

2. **Check DNS policy in pod**:
```yaml
spec:
  dnsPolicy: ClusterFirst
```

### Service Unreachable

**Symptom**: Cannot connect to external services

**Diagnosis**:
```bash
# Check node can reach internet
kubectl exec training-0 -- curl -s https://google.com

# Check VPC endpoints
aws ec2 describe-vpc-endpoints --vpc-id vpc-xxxxx
```

**Solutions**:

1. **Check NAT Gateway configuration**
2. **Verify security group outbound rules**
3. **Add required VPC endpoints**

## Storage Issues

### PVC Not Bound

**Symptom**: PersistentVolumeClaim stuck in Pending

```bash
kubectl get pvc
# NAME      STATUS    VOLUME   CAPACITY   STORAGECLASS
# data-pvc  Pending                        fsx-lustre
```

**Diagnosis**:
```bash
kubectl describe pvc data-pvc
# Check events for errors
```

**Solutions**:

1. **Check StorageClass exists**:
```bash
kubectl get storageclass
```

2. **Verify FSx CSI driver installed**:
```bash
kubectl get pods -n kube-system | grep fsx
```

3. **Check subnet and security group in StorageClass**

### Mount Failures

**Symptom**: Container cannot mount volume

```
MountVolume.SetUp failed: mount failed
```

**Solutions**:

1. **Check FSx filesystem is available**:
```bash
aws fsx describe-file-systems --file-system-ids fs-xxxxx
```

2. **Verify security group allows FSx traffic (TCP 988)**

3. **Check Lustre client on nodes**:
```bash
# On node
lsmod | grep lustre
```

## GPU/Accelerator Issues

### CUDA Out of Memory

**Symptom**: CUDA memory allocation fails

```
RuntimeError: CUDA out of memory. Tried to allocate X GiB
```

**Solutions**:

1. **Reduce batch size**
2. **Enable gradient checkpointing**
3. **Use mixed precision training**
4. **Clear GPU cache**:
```python
torch.cuda.empty_cache()
```

### GPU Driver Mismatch

**Symptom**: CUDA version incompatibility

```
CUDA error: CUDA driver version is insufficient
```

**Solutions**:

1. **Check driver version on node**:
```bash
nvidia-smi
```

2. **Use compatible container image**:
```yaml
image: 763104351884.dkr.ecr.us-west-2.amazonaws.com/pytorch-training:2.1.0-gpu-py310-cu118-ubuntu20.04-sagemaker
```

### NVLink/NVSwitch Errors

**Symptom**: GPU-to-GPU communication errors

```
NCCL WARN P2P not supported between GPU X and GPU Y
```

**Diagnosis**:
```bash
# On node
nvidia-smi topo -m
nvidia-smi nvlink -s
```

**Solutions**:

1. **Use correct NCCL settings**:
```yaml
env:
  - name: NCCL_P2P_LEVEL
    value: "NVL"
```

2. **Verify all GPUs healthy**:
```bash
nvidia-smi -q
```

## Job Failures

### Job Stuck in Creating

**Symptom**: PyTorchJob stuck in Creating status

```bash
kubectl get pytorchjobs
# NAME       STATUS     AGE
# training   Creating   30m
```

**Diagnosis**:
```bash
kubectl describe pytorchjob training
kubectl get pods -l pytorch-job-name=training
```

**Solutions**:

1. **Check if master pod started**
2. **Verify resource requests can be satisfied**
3. **Check for image pull errors**

### Partial Job Failure

**Symptom**: Some workers fail while others succeed

**Diagnosis**:
```bash
# Check all worker statuses
kubectl get pods -l pytorch-job-name=training

# Check failed worker logs
kubectl logs training-worker-2 --previous
```

**Solutions**:

1. **Enable restartPolicy: OnFailure**
2. **Add health checks**
3. **Use fault-tolerant training (elastic)**

## Collecting Diagnostics

### Generate Support Bundle

```bash
#!/bin/bash
# collect-diagnostics.sh

OUTPUT_DIR="hyperpod-diagnostics-$(date +%Y%m%d-%H%M%S)"
mkdir -p $OUTPUT_DIR

# Cluster info
kubectl cluster-info dump > $OUTPUT_DIR/cluster-info.txt
kubectl get nodes -o yaml > $OUTPUT_DIR/nodes.yaml
kubectl get pods --all-namespaces -o yaml > $OUTPUT_DIR/pods.yaml

# Events
kubectl get events --all-namespaces --sort-by='.lastTimestamp' > $OUTPUT_DIR/events.txt

# Resource usage
kubectl top nodes > $OUTPUT_DIR/node-usage.txt
kubectl top pods --all-namespaces > $OUTPUT_DIR/pod-usage.txt

# Device plugin logs
kubectl logs -n kube-system -l app=nvidia-device-plugin --tail=1000 > $OUTPUT_DIR/nvidia-plugin.log

# Pack archive
tar -czf $OUTPUT_DIR.tar.gz $OUTPUT_DIR
echo "Diagnostics saved to $OUTPUT_DIR.tar.gz"
```

### Node-Level Diagnostics

```bash
# Connect to node
aws ssm start-session --target i-xxxxx

# System info
uname -a
cat /etc/os-release

# GPU info
nvidia-smi -q > /tmp/nvidia-smi.txt

# Network info
ip addr
ip route

# Disk usage
df -h
lsblk

# Process list
ps aux

# Kernel messages
dmesg | tail -100
```

## Getting Help

1. **Check AWS documentation**: SageMaker HyperPod User Guide
2. **Review CloudWatch logs**: /aws/sagemaker/Clusters/<cluster-name>
3. **Contact AWS Support**: Include diagnostics bundle
