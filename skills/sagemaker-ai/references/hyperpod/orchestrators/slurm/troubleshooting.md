# Slurm Troubleshooting Guide

This guide covers common issues and solutions for HyperPod with Slurm orchestration.

## Diagnostic Commands

### Cluster Health

```bash
# Check Slurm controller status
systemctl status slurmctld
systemctl status slurmd

# View Slurm logs
sudo tail -f /var/log/slurm/slurmctld.log
sudo tail -f /var/log/slurm/slurmd.log

# Check all nodes
sinfo -N -l

# Check node details
scontrol show nodes

# Check partitions
scontrol show partitions
```

### Job Diagnostics

```bash
# Why is job pending?
squeue -j <jobid> --format="%r"

# Job history
sacct -j <jobid> --format=JobID,State,ExitCode,Elapsed,MaxRSS

# Detailed job info
scontrol show job <jobid>

# Job efficiency
seff <jobid>
```

## Node Issues

### Node Down/Drained

**Symptom**: Node shows as `down` or `drained`

```bash
sinfo
# PARTITION AVAIL  TIMELIMIT  NODES  STATE NODELIST
# gpu          up   infinite      3  idle  ip-10-0-1-[10-12]
# gpu          up   infinite      1  down  ip-10-0-1-13
```

**Diagnosis**:
```bash
# Check node reason
scontrol show node ip-10-0-1-13 | grep Reason

# Check slurmd on node
ssh ip-10-0-1-13 "systemctl status slurmd"
```

**Solutions**:

1. **Resume node**:
```bash
sudo scontrol update nodename=ip-10-0-1-13 state=resume
```

2. **Restart slurmd on node**:
```bash
ssh ip-10-0-1-13 "sudo systemctl restart slurmd"
```

3. **Check for hardware issues**:
```bash
ssh ip-10-0-1-13 "nvidia-smi"
ssh ip-10-0-1-13 "dmesg | tail -50"
```

### Node Not Registering

**Symptom**: New node not appearing in `sinfo`

**Diagnosis**:
```bash
# On controller
sudo tail -f /var/log/slurm/slurmctld.log | grep "node"

# On node
sudo tail -f /var/log/slurm/slurmd.log
```

**Common Causes**:

| Issue | Solution |
|-------|----------|
| slurmd not running | `sudo systemctl start slurmd` |
| Hostname mismatch | Check `/etc/hosts` and `slurm.conf` |
| Network issue | Check security groups, DNS |
| Config mismatch | Sync `slurm.conf` across cluster |

### GPU Not Detected

**Symptom**: GPUs not showing in Slurm

```bash
sinfo -o "%N %G"
# NODELIST     GRES
# ip-10-0-1-10 (null)  # Should show gpu:8
```

**Diagnosis**:
```bash
# Check nvidia-smi on node
ssh ip-10-0-1-10 "nvidia-smi"

# Check gres.conf
cat /etc/slurm/gres.conf
```

**Solutions**:

1. **Fix gres.conf**:
```bash
# /etc/slurm/gres.conf
AutoDetect=nvml
```

2. **Restart slurmd**:
```bash
sudo systemctl restart slurmd
```

3. **Reconfigure Slurm**:
```bash
sudo scontrol reconfigure
```

## Job Issues

### Job Pending - Resources

**Symptom**: Job stuck in pending state

```bash
squeue -j 12345
# JOBID  STATE     REASON
# 12345  PENDING   (Resources)
```

**Diagnosis**:
```bash
# Check requested resources
scontrol show job 12345 | grep -E "NumNodes|NumCPUs|Gres"

# Check available resources
sinfo -N -o "%N %C %G %m %e"
```

**Solutions**:

1. **Reduce resource request**:
```bash
#SBATCH --nodes=2      # Reduce from 4
#SBATCH --gpus=16      # Reduce from 32
```

2. **Wait for resources**:
```bash
# Check when resources become available
squeue -u $USER --start
```

3. **Use different partition**:
```bash
#SBATCH --partition=other-partition
```

### Job Pending - Priority

**Symptom**: Job pending due to priority

```bash
squeue -j 12345 --format="%r"
# (Priority)
```

**Solutions**:

1. **Wait for higher priority jobs**
2. **Request backfill-friendly resources**:
```bash
#SBATCH --time=2:00:00  # Shorter time allows backfill
```

### Job Fails Immediately

**Symptom**: Job exits with error right after starting

**Diagnosis**:
```bash
# Check exit code
sacct -j 12345 --format=JobID,State,ExitCode

# Check error log
cat logs/training_12345.err

# Check system logs
ssh <node> "dmesg | tail -50"
```

**Common Exit Codes**:

| Code | Meaning | Solution |
|------|---------|----------|
| 1 | General error | Check application logs |
| 2 | Misuse of command | Check script syntax |
| 126 | Permission denied | `chmod +x script.sh` |
| 127 | Command not found | Check PATH, module loads |
| 137 | Killed (OOM) | Increase memory |
| 139 | Segfault | Check CUDA/driver |

### Job Timeout

**Symptom**: Job killed due to time limit

```bash
sacct -j 12345
# JOBID    STATE      ELAPSED
# 12345    TIMEOUT    24:00:01
```

**Solutions**:

1. **Increase time limit**:
```bash
#SBATCH --time=48:00:00
```

2. **Implement checkpointing**:
```bash
#SBATCH --signal=B:USR1@300  # Signal 5 min before timeout
```

3. **Requeue job**:
```bash
#SBATCH --requeue
```

## Distributed Training Issues

### NCCL Initialization Failure

**Symptom**: Training hangs or fails during NCCL init

```
NCCL WARN Bootstrap : no socket interface found
[E] NCCL error: unhandled system error
```

**Solutions**:

1. **Set correct network interface**:
```bash
export NCCL_SOCKET_IFNAME=eth0
```

2. **Disable InfiniBand** (if not available):
```bash
export NCCL_IB_DISABLE=1
```

3. **Enable debug logging**:
```bash
export NCCL_DEBUG=INFO
```

### NCCL Timeout

**Symptom**: Training hangs during communication

```
Watchdog caught collective operation timeout
NCCL WARN Timeout
```

**Solutions**:

1. **Increase timeout**:
```bash
export NCCL_TIMEOUT=1800
```

2. **Check network connectivity**:
```bash
# From worker node
ping <master_node>
nc -zv <master_node> 29500
```

3. **Verify firewall/security groups**

### Master Address Incorrect

**Symptom**: Workers can't connect to master

```
Connection refused
Failed to connect to master
```

**Solutions**:

1. **Fix master address derivation**:
```bash
export MASTER_ADDR=$(scontrol show hostname $SLURM_NODELIST | head -n1)
```

2. **Use consistent port**:
```bash
export MASTER_PORT=29500  # Same across all nodes
```

3. **Verify hostname resolution**:
```bash
getent hosts $MASTER_ADDR
```

### Rank/World Size Mismatch

**Symptom**: Process rank errors

```
RuntimeError: Each process must have a unique rank
World size mismatch
```

**Solutions**:

1. **Calculate correctly**:
```bash
export WORLD_SIZE=$((SLURM_NNODES * 8))
export RANK=$SLURM_PROCID
export LOCAL_RANK=$SLURM_LOCALID
```

2. **Use torchrun** (handles automatically):
```bash
srun torchrun --nproc_per_node=8 train.py
```

## GPU Issues

### CUDA Out of Memory

**Symptom**: GPU memory allocation fails

```
RuntimeError: CUDA out of memory
Tried to allocate X GiB
```

**Solutions**:

1. **Reduce batch size**
2. **Enable gradient checkpointing**
3. **Use mixed precision**:
```python
from torch.cuda.amp import autocast
with autocast():
    output = model(input)
```
4. **Clear cache**:
```python
torch.cuda.empty_cache()
```

### GPU Compute Mode

**Symptom**: Only one process can use GPU

```bash
nvidia-smi -q | grep "Compute Mode"
# Compute Mode: Exclusive_Process
```

**Solution**:
```bash
# Set to default mode
sudo nvidia-smi -c 0
```

### EFA Communication Errors

**Symptom**: EFA-related errors

```
fi_getinfo: -61
FI_PROVIDER not available
```

**Solutions**:

1. **Verify EFA availability**:
```bash
fi_info -p efa
```

2. **Check security group**: Allow all traffic from self

3. **Verify instance type supports EFA**

## File System Issues

### FSx Mount Failed

**Symptom**: Cannot access `/fsx`

```
mount: /fsx: bad option
ls: cannot access '/fsx': Transport endpoint is not connected
```

**Solutions**:

1. **Check FSx status**:
```bash
aws fsx describe-file-systems --file-system-ids fs-xxxxx
```

2. **Remount filesystem**:
```bash
sudo umount -l /fsx
sudo mount -t lustre -o noatime,flock \
    fs-xxxxx.fsx.region.amazonaws.com@tcp:/mountname /fsx
```

3. **Verify Lustre client**:
```bash
lsmod | grep lustre
```

### Storage Full

**Symptom**: Disk space errors

```
No space left on device
```

**Diagnosis**:
```bash
df -h
du -sh /fsx/*
```

**Solutions**:

1. **Clean up old checkpoints**:
```bash
find /fsx/checkpoints -mtime +7 -delete
```

2. **Compress logs**:
```bash
gzip /fsx/logs/*.log
```

3. **Use local NVMe for temp files**:
```bash
export TMPDIR=/local/tmp
```

## Performance Issues

### Low GPU Utilization

**Symptom**: GPUs underutilized

```bash
nvidia-smi
# GPU-Util: 20%  # Should be >90%
```

**Solutions**:

1. **Increase batch size**
2. **Use more data workers**:
```python
DataLoader(dataset, num_workers=8, pin_memory=True)
```
3. **Profile data loading**
4. **Check CPU bottleneck**:
```bash
htop
```

### Slow Inter-Node Communication

**Symptom**: Training scaling poorly

**Diagnosis**:
```bash
# Run NCCL test
/opt/nccl-tests/build/all_reduce_perf -b 8 -e 128M -f 2 -g 8
```

**Solutions**:

1. **Enable EFA**:
```bash
export FI_PROVIDER=efa
export FI_EFA_USE_DEVICE_RDMA=1
```

2. **Use NCCL tree algorithm for large messages**:
```bash
export NCCL_ALGO=Tree
```

3. **Verify placement group**

## Collecting Diagnostics

### Generate Support Bundle

```bash
#!/bin/bash
# collect-slurm-diagnostics.sh

OUTPUT_DIR="slurm-diagnostics-$(date +%Y%m%d-%H%M%S)"
mkdir -p $OUTPUT_DIR

# Slurm state
sinfo -a > $OUTPUT_DIR/sinfo.txt
squeue -a > $OUTPUT_DIR/squeue.txt
scontrol show nodes > $OUTPUT_DIR/nodes.txt
scontrol show partitions > $OUTPUT_DIR/partitions.txt
scontrol show config > $OUTPUT_DIR/config.txt

# Recent job history
sacct --starttime=$(date -d "7 days ago" +%Y-%m-%d) \
    --format=JobID,JobName,State,ExitCode,Elapsed,Start,End \
    > $OUTPUT_DIR/job-history.txt

# Slurm logs
sudo cp /var/log/slurm/slurmctld.log $OUTPUT_DIR/
sudo cp /var/log/slurm/slurmd.log $OUTPUT_DIR/

# System info
uname -a > $OUTPUT_DIR/system-info.txt
nvidia-smi -q > $OUTPUT_DIR/nvidia-smi.txt 2>&1

# Create archive
tar -czf $OUTPUT_DIR.tar.gz $OUTPUT_DIR
echo "Diagnostics saved to $OUTPUT_DIR.tar.gz"
```

### Debug Mode Job

```bash
#!/bin/bash
#SBATCH --job-name=debug
#SBATCH --nodes=1
#SBATCH --gpus=8
#SBATCH --time=1:00:00

set -x  # Print all commands

# System info
echo "=== HOSTNAME ==="
hostname

echo "=== NVIDIA-SMI ==="
nvidia-smi

echo "=== EFA ==="
fi_info -p efa

echo "=== ENVIRONMENT ==="
env | sort

echo "=== STORAGE ==="
df -h

echo "=== TEST CUDA ==="
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, Devices: {torch.cuda.device_count()}')"

echo "=== TEST NCCL ==="
python -c "import torch.distributed as dist; dist.init_process_group('nccl'); print('NCCL OK')"
```

## Getting Help

1. **Check Slurm documentation**: https://slurm.schedmd.com/
2. **Review CloudWatch logs**: /aws/sagemaker/Clusters/<cluster-name>
3. **Contact AWS Support**: Include diagnostics bundle
