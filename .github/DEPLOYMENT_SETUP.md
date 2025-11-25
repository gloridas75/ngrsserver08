# GitHub Actions Auto-Deploy Setup Guide

## Overview

This setup enables **automatic deployment** to your EC2 server whenever you push code to the `main` branch. No more manual SSH and Docker rebuild!

## How It Works

```
┌─────────────┐      ┌──────────────┐      ┌─────────────────┐
│   git push  │─────>│ GitHub       │─────>│ GitHub Actions  │
│   to main   │      │ Repository   │      │ (CI/CD Runner)  │
└─────────────┘      └──────────────┘      └─────────────────┘
                                                      │
                                                      │ SSH
                                                      ▼
                                            ┌─────────────────┐
                                            │ EC2 Server      │
                                            │ - git pull      │
                                            │ - docker build  │
                                            │ - docker run    │
                                            └─────────────────┘
```

## Setup Steps

### 1. Add GitHub Secrets

You need to add your EC2 SSH credentials to GitHub repository secrets:

1. **Go to your GitHub repository**:
   ```
   https://github.com/gloridas75/ngrsserver08
   ```

2. **Navigate to Settings → Secrets and variables → Actions**

3. **Add the following secrets** (click "New repository secret"):

   | Secret Name | Value | Description |
   |------------|-------|-------------|
   | `EC2_HOST` | `ec2-47-128-231-85.ap-southeast-1.compute.amazonaws.com` | Your EC2 public hostname |
   | `EC2_USERNAME` | `ubuntu` | SSH username |
   | `EC2_SSH_KEY` | (Your private key content) | Full SSH private key |

### 2. Get Your SSH Private Key

On your Mac, run:

```bash
# Display your SSH private key
cat ~/.ssh/id_rsa
# or if you use a different key:
cat ~/.ssh/ngrs-server-key  # or whatever key name you use
```

Copy the **entire output** including:
```
-----BEGIN OPENSSH PRIVATE KEY-----
...
-----END OPENSSH PRIVATE KEY-----
```

Paste this into the `EC2_SSH_KEY` secret.

### 3. Verify GitHub Actions is Enabled

1. Go to **Actions** tab in your repository
2. You should see "Deploy to EC2" workflow
3. If disabled, click "I understand my workflows, go ahead and enable them"

### 4. Test the Workflow

#### Option A: Push a small change
```bash
cd /Users/glori/1\ Anthony_Workspace/My\ Developments/NGRS/ngrs-solver-v0.7/ngrssolver
git add .github/workflows/deploy.yml
git commit -m "feat: Add automated deployment via GitHub Actions"
git push origin main
```

#### Option B: Manually trigger
1. Go to **Actions** tab
2. Click "Deploy to EC2"
3. Click "Run workflow" → "Run workflow"

### 5. Monitor Deployment

1. Go to **Actions** tab in GitHub
2. Click on the latest workflow run
3. Watch the deployment logs in real-time
4. You'll see:
   - ✓ Checkout code
   - ✓ Deploy to EC2 via SSH
   - Docker build progress
   - Container startup
   - Health check results

## What Gets Automated

Every push to `main` branch will automatically:
1. ✅ Pull latest code on server
2. ✅ Stop old Docker container
3. ✅ Build new Docker image
4. ✅ Start new container
5. ✅ Run health check
6. ✅ Clean up old images

**Deployment time**: ~2-3 minutes

## Troubleshooting

### If workflow fails:

1. **Check GitHub Actions logs**:
   - Actions tab → Click failed run → View details

2. **Common issues**:

   | Error | Solution |
   |-------|----------|
   | "Permission denied (publickey)" | Check `EC2_SSH_KEY` secret matches your actual private key |
   | "Host key verification failed" | SSH key might be wrong or GitHub Actions runner blocked |
   | "Docker build failed" | Check if Dockerfile has errors - test locally first |
   | "Container failed to start" | Port 8080 might be in use - check logs in Actions output |

3. **Manual override**: You can always SSH manually if needed:
   ```bash
   ssh ngrs-server "cd /home/ubuntu/ngrssolver && git pull && docker-compose up -d --build"
   ```

## Workflow Configuration

The workflow file is located at:
```
.github/workflows/deploy.yml
```

### Key Features:

- **Triggers**: Automatic on push to `main`, or manual via UI
- **Timeout**: 10 minutes max
- **Health Check**: Verifies API is responding after deployment
- **Cleanup**: Removes old unused Docker images
- **Logging**: Detailed logs for debugging

### Customization:

You can modify the workflow to:
- Deploy to staging first, then production
- Run tests before deploying
- Send Slack/email notifications
- Deploy only on version tags (e.g., `v1.0.0`)

## Security Notes

🔒 **SSH Key Security**:
- GitHub Secrets are encrypted
- Only visible to workflow runs
- Never exposed in logs
- Can be rotated anytime

🔐 **Best Practices**:
- Use a dedicated deploy key (not your personal SSH key)
- Rotate keys periodically
- Monitor Actions logs for suspicious activity

## Alternative: Webhook-Based Deployment

If you prefer **not to use GitHub Actions**, you can set up a webhook listener on your server:

```bash
# Install webhook listener
cd /home/ubuntu
git clone https://github.com/adnanh/webhook
cd webhook
go build

# Create webhook script
cat > deploy-hook.sh << 'EOF'
#!/bin/bash
cd /home/ubuntu/ngrssolver
git pull
docker stop ngrs-solver-api
docker rm ngrs-solver-api
docker build -t ngrs-solver:latest .
docker run -d --name ngrs-solver-api -p 8080:8080 ... ngrs-solver:latest
EOF

chmod +x deploy-hook.sh
```

Then configure GitHub webhook to call your server on push events.

**Pros**: No GitHub Actions minutes used  
**Cons**: Need to keep webhook service running, manage security, open additional port

## Status Badge (Optional)

Add deployment status badge to your README:

```markdown
![Deploy Status](https://github.com/gloridas75/ngrsserver08/actions/workflows/deploy.yml/badge.svg)
```

Shows: ✅ if latest deployment succeeded, ❌ if failed

## Next Steps

1. ✅ Add GitHub secrets
2. ✅ Push workflow file to trigger first deployment
3. ✅ Monitor deployment in Actions tab
4. ✅ Test API after deployment: `curl http://your-server:8080/health`
5. 🎉 Enjoy automatic deployments!

---

**Questions?** Check the GitHub Actions logs first - they're very detailed!
