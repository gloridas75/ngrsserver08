# EC2 Deployment with GitHub CI/CD

Automated deployment of NGRS Solver to EC2 using GitHub Actions.

---

## Deployment Flow

```
Your Mac → Push to GitHub → GitHub Actions → Auto-deploy to EC2 ✨
```

Every push to `main` branch automatically deploys to your EC2 instance!

---

## Setup Steps

### 1. Create EC2 Instance

**Launch Ubuntu 22.04 LTS**:
- Instance type: `t3.medium` (or `t3.small` for testing)
- Storage: 20 GB
- Security Group:
  - Port 22 (SSH) - Your IP
  - Port 80 (HTTP) - Public
  - Port 8080 (API) - Public (or 0.0.0.0/0 for testing)

**Save your SSH key**: `my-ec2-key.pem`

---

### 2. Run Initial Setup on EC2

SSH into your new EC2 instance:

```bash
ssh -i my-ec2-key.pem ubuntu@<YOUR_EC2_IP>
```

Download and run the setup script:

```bash
# Download setup script
curl -O https://raw.githubusercontent.com/gloridas75/ngrsserver08/main/deploy/ec2-initial-setup.sh

# Make executable and run
chmod +x ec2-initial-setup.sh
./ec2-initial-setup.sh
```

**What it does**:
- ✅ Installs Docker, Python, Git
- ✅ Starts Redis container
- ✅ Clones your GitHub repo
- ✅ Installs dependencies
- ✅ Creates systemd service
- ✅ Starts API + workers

**Prompts**:
- GitHub repo URL: `https://github.com/gloridas75/ngrsserver08.git`
- Auto-pull on reboot: `y` (recommended)

---

### 3. Configure GitHub Actions Secrets

In your GitHub repo, go to **Settings → Secrets and variables → Actions** and add:

| Secret Name | Value | Example |
|-------------|-------|---------|
| `EC2_HOST` | Your EC2 public IP | `52.12.34.56` |
| `EC2_USER` | SSH username | `ubuntu` |
| `EC2_SSH_KEY` | Private key content | Contents of `my-ec2-key.pem` |

**To get SSH key content**:
```bash
cat my-ec2-key.pem
```

Copy **entire content** including:
```
-----BEGIN RSA PRIVATE KEY-----
...
-----END RSA PRIVATE KEY-----
```

---

### 4. Push Code to GitHub

From your Mac:

```bash
cd /Users/glori/1\ Anthony_Workspace/My\ Developments/NGRS/ngrs-solver-v0.7/ngrssolver

# Initialize git (if not already)
git init
git add .
git commit -m "Initial commit"

# Add remote (new repo)
git remote add origin https://github.com/gloridas75/ngrsserver08.git

# Push to GitHub
git push -u origin main
```

**GitHub Actions will automatically**:
1. Detect the push
2. SSH into your EC2
3. Pull latest code
4. Restart services
5. Run health check

---

### 5. Monitor Deployment

Watch the deployment in GitHub:

1. Go to your repo: `https://github.com/gloridas75/ngrsserver08`
2. Click **Actions** tab
3. See the "Deploy to EC2" workflow running

**Deployment takes ~30 seconds**

---

## Testing After Deployment

```bash
# Health check (from anywhere)
curl http://<YOUR_EC2_IP>:8080/health

# Check stats
curl http://<YOUR_EC2_IP>:8080/solve/async/stats | python3 -m json.tool

# Submit test job
curl -X POST http://<YOUR_EC2_IP>:8080/solve/async \
  -H "Content-Type: application/json" \
  -d '{
    "input_json": {
      "schemaVersion": "0.70",
      "planningReference": "TEST",
      ...
    }
  }'
```

---

## Making Updates

### Automatic Deployment (Recommended)

Just push to GitHub:

```bash
# Make changes
vim src/solver.py

# Commit and push
git add .
git commit -m "Updated solver logic"
git push

# GitHub Actions deploys automatically! 🚀
```

### Manual Deployment (if needed)

SSH to EC2:

```bash
ssh ubuntu@<EC2_IP>

cd ~/ngrssolver
git pull origin main
sudo systemctl restart ngrs-api
```

---

## Architecture

```
┌─────────────────────────────────────┐
│         Your Mac                    │
│  git push → GitHub                  │
└────────────────┬────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│       GitHub Actions                │
│  - Triggered on push                │
│  - SSH to EC2                       │
│  - Pull code                        │
│  - Restart service                  │
└────────────────┬────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│       EC2 Instance                  │
│  ┌──────────┐   ┌──────────────┐   │
│  │  Redis   │◄──┤ API + Workers│   │
│  │ (Docker) │   │  (systemd)   │   │
│  └──────────┘   └──────────────┘   │
└─────────────────────────────────────┘
```

---

## Monitoring

### Check Deployment Status

**On GitHub**:
- Actions tab → See workflow runs
- Green ✓ = successful deployment
- Red ✗ = failed (check logs)

**On EC2**:
```bash
# Service status
sudo systemctl status ngrs-api

# Live logs
sudo journalctl -u ngrs-api -f

# Redis
docker ps | grep ngrs-redis
```

### Check API Health

```bash
# From EC2
curl http://localhost:8080/health
curl http://localhost:8080/solve/async/stats

# From anywhere
curl http://<EC2_IP>:8080/health
```

---

## Troubleshooting

### GitHub Actions failing

**Check secrets**:
- Go to Settings → Secrets
- Verify `EC2_HOST`, `EC2_USER`, `EC2_SSH_KEY` are set

**Test SSH manually**:
```bash
ssh -i my-ec2-key.pem ubuntu@<EC2_IP>
```

### Service not starting

**Check logs on EC2**:
```bash
sudo journalctl -u ngrs-api -n 50
```

**Common issues**:
- Python dependencies not installed
- Redis not running
- Port 8080 already in use

**Fix**:
```bash
# Reinstall dependencies
cd ~/ngrssolver
pip3 install -r requirements.txt

# Restart Redis
docker restart ngrs-redis

# Restart API
sudo systemctl restart ngrs-api
```

### Deployment successful but API not responding

**Check security group**:
- Ensure port 8080 is open in EC2 Security Group
- Source: `0.0.0.0/0` (or your IP range)

**Check if API is listening**:
```bash
sudo netstat -tlnp | grep 8080
```

---

## Manual Trigger

You can manually trigger deployment from GitHub:

1. Go to **Actions** tab
2. Select "Deploy to EC2" workflow
3. Click **Run workflow** button
4. Select branch: `main`
5. Click **Run workflow**

---

## Rollback

If a deployment breaks something:

```bash
# SSH to EC2
ssh ubuntu@<EC2_IP>

# Go to repo
cd ~/ngrssolver

# Revert to previous commit
git log  # Find previous commit hash
git reset --hard <commit-hash>

# Restart service
sudo systemctl restart ngrs-api
```

Or redeploy from GitHub:
1. Revert commit on GitHub
2. Push revert → auto-deploys

---

## Advanced: Multiple Environments

### Production + Staging

**Create 2 EC2 instances**:
- Production: Use `main` branch
- Staging: Use `develop` branch

**Create 2 workflows**:

`.github/workflows/deploy-production.yml`:
```yaml
on:
  push:
    branches:
      - main
# ... deploy to production EC2
```

`.github/workflows/deploy-staging.yml`:
```yaml
on:
  push:
    branches:
      - develop
# ... deploy to staging EC2
```

---

## Cost

| Item | Cost |
|------|------|
| EC2 t3.small | ~$15/month |
| EC2 t3.medium | ~$30/month |
| GitHub Actions | Free (2000 min/month) |
| Storage | ~$2/month |

**Total**: $17-32/month

**Compared to App Runner + ElastiCache**: Save $60-80/month! 💰

---

## Next Steps

1. ✅ Create new GitHub repo: `ngrsserver08`
2. ✅ Launch EC2 instance
3. ✅ Run `ec2-initial-setup.sh` on EC2
4. ✅ Configure GitHub secrets
5. ✅ Push code → Auto-deploy!

---

## Files Reference

| File | Purpose |
|------|---------|
| `.github/workflows/deploy-ec2.yml` | GitHub Actions workflow |
| `deploy/ec2-initial-setup.sh` | One-time EC2 setup |
| `deploy/health-check.sh` | Health check script |

---

## Support

- **GitHub Actions logs**: Actions tab in repo
- **EC2 logs**: `sudo journalctl -u ngrs-api -f`
- **Test locally**: `deploy/start-solver.sh`
