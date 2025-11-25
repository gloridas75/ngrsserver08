# AWS Deployment Guide: Redis-Based Async Solver

## Overview

This guide covers deploying the NGRS solver with Redis-based async architecture on AWS.

**Key Challenge**: AWS App Runner has limitations with Redis and background workers.

---

## Architecture Options

### Option 1: Distributed (Recommended) ⭐

**Best for**: Production, high traffic, independent scaling

```
Internet
   │
   ▼
┌─────────────────────┐
│   AWS App Runner    │
│   API Server Only   │
│   (No workers)      │
└──────────┬──────────┘
           │
           ▼
┌──────────────────────────┐
│  AWS ElastiCache Redis   │
│  (Managed Redis)         │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  ECS Fargate/EC2         │
│  Worker Processes        │
│  (Auto-scaling)          │
└──────────────────────────┘
```

**Pros**:
- ✅ Independent scaling (API vs Workers)
- ✅ Workers scale based on queue length
- ✅ Better fault tolerance
- ✅ Efficient resource utilization

**Cons**:
- More complex setup
- Multiple services to manage

---

### Option 2: All-in-One (Simpler)

**Best for**: Development, low traffic, simple deployment

```
Internet
   │
   ▼
┌─────────────────────────┐
│   AWS App Runner        │
│   - API Server          │
│   - Workers (same pod)  │
└──────────┬──────────────┘
           │
           ▼
┌──────────────────────────┐
│  AWS ElastiCache Redis   │
│  (Managed Redis)         │
└──────────────────────────┘
```

**Pros**:
- ✅ Simple deployment
- ✅ Single service to manage
- ✅ Lower cost for low traffic

**Cons**:
- ⚠️ API and workers share resources
- ⚠️ Can't scale independently
- ⚠️ Workers stopped when API restarts

---

## Option 1: Distributed Deployment (Recommended)

### Step 1: Create ElastiCache Redis Cluster

#### Via AWS Console:
1. Go to ElastiCache → Redis
2. Click "Create"
3. Configure:
   - **Engine**: Redis 7.x
   - **Cluster mode**: Disabled (simpler) or Enabled (more resilient)
   - **Node type**: cache.t3.micro (start small)
   - **Number of replicas**: 1-2 (for HA)
   - **Multi-AZ**: Enabled (recommended)
4. **VPC Settings**:
   - Choose VPC
   - Create subnet group (private subnets)
   - Security group: Allow port 6379 from App Runner and ECS
5. **Encryption**: At-rest and in-transit (recommended)
6. Create cluster

#### Via CLI:
```bash
aws elasticache create-replication-group \
  --replication-group-id ngrs-redis \
  --replication-group-description "NGRS Solver Redis Queue" \
  --engine redis \
  --cache-node-type cache.t3.micro \
  --num-cache-clusters 2 \
  --automatic-failover-enabled \
  --multi-az-enabled \
  --security-group-ids sg-xxxxx \
  --cache-subnet-group-name ngrs-redis-subnet
```

**Note the Primary Endpoint**: `ngrs-redis.xxxxx.cache.amazonaws.com:6379`

---

### Step 2: Deploy API Server to App Runner

#### 2.1: Update apprunner.yaml

```yaml
version: 1.0
runtime: python3
build:
  commands:
    build:
      - pip install --upgrade pip
      - pip install -r requirements.txt
run:
  runtime-version: 3.11
  command: python -m uvicorn src.api_server:app --host 0.0.0.0 --port 8080
  network:
    port: 8080
    env: 
      - name: START_WORKERS
        value: "false"  # ← Disable workers in App Runner
      - name: REDIS_URL
        value: "ngrs-redis.xxxxx.cache.amazonaws.com:6379"
      - name: REDIS_PASSWORD
        value: "your-password-if-enabled"
      - name: RESULT_TTL_SECONDS
        value: "3600"
      - name: SOLVER_WORKERS
        value: "0"  # ← Not used when START_WORKERS=false
```

#### 2.2: Deploy to App Runner

**Via Console**:
1. Go to App Runner → Create service
2. Source: ECR or GitHub
3. Configure environment variables (see above)
4. **VPC Connector**: Create/select to access ElastiCache
5. Deploy

**Via CLI**:
```bash
aws apprunner create-service \
  --service-name ngrs-solver-api \
  --source-configuration file://apprunner-source.json \
  --instance-configuration Cpu=1vCPU,Memory=2GB \
  --network-configuration EgressConfiguration={VpcConnectorArn=arn:aws:...}
```

---

### Step 3: Deploy Workers to ECS

#### 3.1: Create ECS Task Definition

**File**: `ecs-worker-task.json`

```json
{
  "family": "ngrs-solver-worker",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [
    {
      "name": "worker",
      "image": "YOUR_ECR_IMAGE:latest",
      "command": ["python", "src/redis_worker.py"],
      "essential": true,
      "environment": [
        {"name": "REDIS_URL", "value": "ngrs-redis.xxxxx.cache.amazonaws.com:6379"},
        {"name": "REDIS_PASSWORD", "value": "your-password"},
        {"name": "RESULT_TTL_SECONDS", "value": "3600"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/ngrs-worker",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "worker"
        }
      }
    }
  ]
}
```

#### 3.2: Create ECS Service

```bash
# Register task definition
aws ecs register-task-definition --cli-input-json file://ecs-worker-task.json

# Create service with auto-scaling
aws ecs create-service \
  --cluster ngrs-cluster \
  --service-name ngrs-workers \
  --task-definition ngrs-solver-worker \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={
    subnets=[subnet-xxx,subnet-yyy],
    securityGroups=[sg-xxx],
    assignPublicIp=DISABLED
  }"
```

#### 3.3: Configure Auto-Scaling (Optional)

**Scale based on queue length**:

```bash
# Create custom CloudWatch metric for queue length
# (requires Lambda to poll Redis and publish metric)

# Create scaling policy
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id service/ngrs-cluster/ngrs-workers \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 1 \
  --max-capacity 10

aws application-autoscaling put-scaling-policy \
  --policy-name scale-on-queue-length \
  --service-namespace ecs \
  --resource-id service/ngrs-cluster/ngrs-workers \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration file://scaling-policy.json
```

---

### Step 4: Networking & Security

#### VPC Configuration

```
┌─────────────────────────────────────────┐
│             VPC (10.0.0.0/16)           │
│                                         │
│  ┌────────────┐      ┌────────────┐    │
│  │ Public     │      │ Private    │    │
│  │ Subnet     │      │ Subnet     │    │
│  │            │      │            │    │
│  │            │      │ ElastiCache│    │
│  │            │      │ ECS Tasks  │    │
│  └────────────┘      └────────────┘    │
│         ▲                   ▲          │
└─────────┼───────────────────┼──────────┘
          │                   │
    ┌─────┴─────┐      ┌──────┴──────┐
    │ App Runner│      │   NAT GW    │
    │  (via VPC │      │ (for egress)│
    │ Connector)│      └─────────────┘
    └───────────┘
```

#### Security Groups

**ElastiCache SG** (ingress):
- Port 6379 from App Runner VPC Connector SG
- Port 6379 from ECS Tasks SG

**ECS Tasks SG** (egress):
- Port 6379 to ElastiCache SG
- Port 443 to Internet (for packages if needed)

---

## Option 2: All-in-One Deployment

### Configuration

**apprunner.yaml**:
```yaml
version: 1.0
runtime: python3
build:
  commands:
    build:
      - pip install --upgrade pip
      - pip install -r requirements.txt
run:
  runtime-version: 3.11
  command: python -m uvicorn src.api_server:app --host 0.0.0.0 --port 8080
  network:
    port: 8080
    env: 
      - name: START_WORKERS
        value: "true"  # ← Enable workers in same container
      - name: REDIS_URL
        value: "ngrs-redis.xxxxx.cache.amazonaws.com:6379"
      - name: REDIS_PASSWORD
        value: "your-password"
      - name: SOLVER_WORKERS
        value: "2"  # ← Number of workers
      - name: RESULT_TTL_SECONDS
        value: "3600"
```

### Deploy

Same as Option 1 Step 2, but with `START_WORKERS=true` and `SOLVER_WORKERS=2`.

**Note**: Workers will run inside the same container as API server.

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `START_WORKERS` | No | `true` | Start workers in API process? |
| `SOLVER_WORKERS` | No | `2` | Number of worker processes |
| `REDIS_URL` | Yes | `localhost:6379` | Redis endpoint |
| `REDIS_DB` | No | `0` | Redis database number |
| `REDIS_PASSWORD` | No | - | Redis auth password |
| `RESULT_TTL_SECONDS` | No | `3600` | Result cache TTL |
| `REDIS_KEY_PREFIX` | No | `ngrs` | Redis key prefix |

---

## Testing Deployment

### 1. Test API Endpoint
```bash
curl https://YOUR_APPRUNNER_URL/health
# Expected: {"status":"ok","timestamp":"..."}

curl https://YOUR_APPRUNNER_URL/solve/async/stats
# Expected: {"total_jobs":0,"queue_length":0,"workers":0,"redis_connected":true}
```

### 2. Submit Test Job
```bash
curl -X POST https://YOUR_APPRUNNER_URL/solve/async \
  -H "Content-Type: application/json" \
  -d '{
    "input_json": {
      "schemaVersion": "0.70",
      "planningReference": "TEST",
      ...
    }
  }'

# Expected: {"job_id":"uuid","status":"queued",...}
```

### 3. Check Workers (ECS)
```bash
# View worker logs
aws logs tail /ecs/ngrs-worker --follow

# Expected output:
# [WORKER-1] Polling Redis queue...
# [WORKER-1] Processing job uuid...
# [WORKER-1] Job completed: OPTIMAL
```

### 4. Monitor Queue
```bash
# Check Redis queue length via stats endpoint
curl https://YOUR_APPRUNNER_URL/solve/async/stats | jq '.queue_length'

# Or directly (if Redis accessible)
redis-cli -h ngrs-redis.xxxxx.cache.amazonaws.com LLEN ngrs:job:queue
```

---

## Cost Estimates

### Option 1: Distributed

| Service | Configuration | Monthly Cost (USD) |
|---------|--------------|-------------------|
| App Runner | 1 vCPU, 2GB RAM | ~$25-50 |
| ElastiCache | cache.t3.micro, 2 nodes | ~$25 |
| ECS Fargate | 0.5 vCPU, 1GB RAM, 2 tasks | ~$30 |
| Data Transfer | Minimal | ~$5 |
| **Total** | | **~$85-110/month** |

### Option 2: All-in-One

| Service | Configuration | Monthly Cost (USD) |
|---------|--------------|-------------------|
| App Runner | 1 vCPU, 2GB RAM | ~$25-50 |
| ElastiCache | cache.t3.micro, 1 node | ~$13 |
| **Total** | | **~$38-63/month** |

**Note**: Actual costs depend on traffic and compute time.

---

## Monitoring & Alerting

### CloudWatch Metrics

**App Runner**:
- CPU/Memory utilization
- Request count
- 4xx/5xx errors

**ECS Workers**:
- CPU/Memory utilization
- Task count
- Task health

**ElastiCache**:
- EngineCPUUtilization
- NetworkBytesIn/Out
- CurrConnections

### Custom Metrics

**Queue Length** (via Lambda):
```python
import boto3
import redis

def lambda_handler(event, context):
    r = redis.Redis(host='ngrs-redis.xxxxx.cache.amazonaws.com')
    queue_length = r.llen('ngrs:job:queue')
    
    cloudwatch = boto3.client('cloudwatch')
    cloudwatch.put_metric_data(
        Namespace='NGRS/Solver',
        MetricData=[{
            'MetricName': 'QueueLength',
            'Value': queue_length,
            'Unit': 'Count'
        }]
    )
```

**Schedule**: Every 1 minute (EventBridge rule)

### Alarms

```bash
# High queue length
aws cloudwatch put-metric-alarm \
  --alarm-name ngrs-high-queue-length \
  --metric-name QueueLength \
  --namespace NGRS/Solver \
  --statistic Average \
  --period 300 \
  --threshold 50 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2

# Worker task count too low
aws cloudwatch put-metric-alarm \
  --alarm-name ngrs-low-worker-count \
  --metric-name DesiredTaskCount \
  --namespace AWS/ECS \
  --dimensions Name=ServiceName,Value=ngrs-workers \
  --statistic Average \
  --period 60 \
  --threshold 1 \
  --comparison-operator LessThanThreshold
```

---

## Troubleshooting

### API can't connect to Redis

**Symptom**: `redis_connected: false` in stats endpoint

**Causes**:
1. VPC Connector not configured
2. Security group blocks port 6379
3. Wrong Redis endpoint

**Fix**:
```bash
# Check VPC connector
aws apprunner describe-service --service-arn ARN | jq '.Service.NetworkConfiguration'

# Test Redis connectivity (from ECS task or EC2 in same VPC)
redis-cli -h ngrs-redis.xxxxx.cache.amazonaws.com ping
```

### Workers not processing jobs

**Symptom**: Queue length grows, jobs stay "queued"

**Causes**:
1. Workers not running (ECS service down)
2. Workers can't connect to Redis
3. Worker process crashed

**Fix**:
```bash
# Check ECS service
aws ecs describe-services --cluster ngrs-cluster --services ngrs-workers

# Check worker logs
aws logs tail /ecs/ngrs-worker --follow

# Check Redis queue
redis-cli -h REDIS_HOST LLEN ngrs:job:queue
redis-cli -h REDIS_HOST LRANGE ngrs:job:queue 0 10
```

### High latency

**Symptom**: Jobs take long to complete

**Causes**:
1. Too few workers
2. Redis overloaded
3. Complex inputs

**Fix**:
```bash
# Scale up workers
aws ecs update-service \
  --cluster ngrs-cluster \
  --service ngrs-workers \
  --desired-count 5

# Check Redis performance
aws cloudwatch get-metric-statistics \
  --namespace AWS/ElastiCache \
  --metric-name EngineCPUUtilization \
  --dimensions Name=CacheClusterId,Value=ngrs-redis-001 \
  --start-time 2025-01-01T00:00:00Z \
  --end-time 2025-01-01T23:59:59Z \
  --period 300 \
  --statistics Average
```

---

## Summary

### ✅ Recommended: Option 1 (Distributed)

**For Production**:
1. **ElastiCache Redis**: Managed, HA, secure
2. **App Runner**: API server only (`START_WORKERS=false`)
3. **ECS Fargate**: Workers with auto-scaling

**Benefits**:
- Independent scaling
- Better fault tolerance
- Efficient resource use
- Queue-based auto-scaling

### ⚠️ Alternative: Option 2 (All-in-One)

**For Dev/Testing/Low Traffic**:
1. **ElastiCache Redis**: Single node
2. **App Runner**: API + workers (`START_WORKERS=true`)

**Trade-offs**:
- Simpler setup
- Lower cost
- Less scalable
- Workers compete with API

---

## Next Steps

1. ✅ **Code Ready**: `START_WORKERS` env var added
2. ⏳ **Setup ElastiCache**: Create Redis cluster
3. ⏳ **Deploy API**: App Runner with VPC connector
4. ⏳ **Deploy Workers**: ECS service (Option 1 only)
5. ⏳ **Test**: Submit jobs, monitor queue
6. ⏳ **Monitor**: CloudWatch alarms, custom metrics

**Documentation**: All deployment files included in `implementation_docs/AWS_*` guides.
