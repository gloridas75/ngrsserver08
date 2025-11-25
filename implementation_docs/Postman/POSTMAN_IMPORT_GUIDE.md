# Postman Collection - Import Guide

## 📦 Files Included

1. **NGRS_Solver_API.postman_collection.json** - Complete API collection
2. **NGRS_Solver_Production.postman_environment.json** - Production environment
3. **NGRS_Solver_Local.postman_environment.json** - Local development environment

## 🚀 Quick Start

### Step 1: Import Collection

1. Open Postman
2. Click **Import** (top left)
3. Drag and drop `NGRS_Solver_API.postman_collection.json`
4. Click **Import**

### Step 2: Import Environment

1. Click **Import** again
2. Drag and drop environment files:
   - `NGRS_Solver_Production.postman_environment.json`
   - `NGRS_Solver_Local.postman_environment.json` (optional)
3. Click **Import**

### Step 3: Select Environment

1. Top right corner: Environment dropdown
2. Select **NGRS Solver - Production**

### Step 4: Configure Variables

1. Click the **👁️ eye icon** (environment quick look)
2. Click **Edit** next to "NGRS Solver - Production"
3. Update variables:
   - `base_url`: Already set to `https://ngrssolver08.comcentricapps.com`
   - `admin_api_key`: Change from `change-me-in-production` to your actual key
   - `job_id`: Leave empty (auto-populated)
4. Click **Save**

## 📚 Collection Structure

### 1. Health & Info (3 requests)
- **Health Check** - Verify API is running
- **API Version** - Get version info
- **Input Schema** - Get JSON schema

### 2. Configuration Optimizer - ICPMP (2 requests)
- **Get Optimal Configurations** - Standard requirements
- **ICPMP - Mixed Shift Types** - Test with mixed D+N shifts

### 3. Synchronous Solve (1 request)
- **Solve Small Problem** - Immediate solving for small datasets

### 4. Asynchronous Solve (5 requests)
- **Submit Async Job** - Submit long-running job
- **Get Job Status** - Check job progress
- **Queue Stats** - Basic queue statistics
- **Queue Stats (Detailed)** - With job UUIDs and timestamps
- **Delete Job** - Remove job from memory

### 5. Admin Operations (1 request)
- **System Reset** - Complete Redis flush + worker restart

### 6. Alternative Input Formats (2 requests)
- **Async - Wrapped Format** - `{"input_json": {...}}`
- **Async - Direct Format** - Direct NGRS input

## 🎯 Quick Test Workflow

### Test 1: Health Check
```
1. Health & Info → Health Check
2. Click "Send"
3. Should return: {"status": "ok", ...}
```

### Test 2: Get Configuration Recommendations
```
1. Configuration Optimizer → Get Optimal Configurations
2. Click "Send"
3. Returns: Top 5 patterns per requirement
```

### Test 3: Async Job Flow
```
1. Asynchronous Solve → Submit Async Job
   - Click "Send"
   - Note: job_id auto-saved to variable
   
2. Asynchronous Solve → Get Job Status
   - Click "Send" (uses saved job_id)
   - Check status: queued → in_progress → completed
   
3. Asynchronous Solve → Get Job Status (again)
   - Once status = "completed"
   - Response includes full solution
   
4. Asynchronous Solve → Delete Job
   - Click "Send"
   - Frees memory
```

### Test 4: Monitor Queue
```
1. Asynchronous Solve → Queue Stats
   - Basic statistics
   
2. Asynchronous Solve → Queue Stats (Detailed)
   - Shows all job UUIDs with timestamps
```

## 🔑 Variables Explained

### Collection Variables
Automatically set by the collection:
- `base_url`: API endpoint URL
- `admin_api_key`: Admin authentication key
- `job_id`: Last created async job (auto-saved)

### Auto-Population
The **Submit Async Job** request includes a test script that automatically saves the job_id:
```javascript
var jsonData = pm.response.json();
if (jsonData.job_id) {
    pm.collectionVariables.set("job_id", jsonData.job_id);
}
```

This means subsequent requests (Get Status, Delete) automatically use the correct job_id!

## 💡 Tips & Tricks

### 1. Use Environments for Different Servers
Switch between production and local:
- **Production**: `https://ngrssolver08.comcentricapps.com`
- **Local**: `http://localhost:8080`

### 2. Save Responses for Reference
Right-click any request → **Save Response** → **Save as example**

### 3. Test Multiple Jobs
Submit several async jobs, then check detailed stats to see all UUIDs

### 4. Admin Reset
**⚠️ Use with caution!**
1. Set `admin_api_key` variable to actual key
2. Run **Admin Operations → System Reset**
3. Confirms: All data deleted, workers restarted

### 5. Run Collection as Test Suite
1. Click **Collection** name
2. Click **Run** (right panel)
3. Select requests to run
4. Click **Run NGRS Solver API**

## 🔍 Request Examples

### Synchronous Solve
```json
POST /solve
{
  "schemaVersion": "0.43",
  "planningHorizon": {...},
  "employees": [...],
  "requirements": [...],
  "constraints": {...}
}
```

### ICPMP Configuration
```json
POST /configure
{
  "planningHorizon": {...},
  "requirements": [
    {
      "id": "REQ_APO_DAY",
      "shiftTypes": ["D"],
      "headcountPerDay": 4
    }
  ]
}
```

### Async Job Submission
```json
POST /solve/async
// Same as synchronous solve input
// OR wrapped format:
{
  "input_json": {...}
}
```

### Admin Reset
```http
POST /admin/reset
x-api-key: your-secret-key
```

## 🐛 Troubleshooting

### "Could not send request"
- Check `base_url` variable is correct
- Verify server is running: test Health Check first
- Check network/firewall

### "401 Unauthorized" (Admin Reset)
- Update `admin_api_key` variable
- Ensure it matches server's ADMIN_API_KEY
- Check header: `x-api-key: {{admin_api_key}}`

### Job Status Returns 404
- Job may have expired (TTL: 3600s)
- Check job_id variable is set
- Verify job was created successfully

### "422 Validation Error"
- Check request body format
- Validate against schema: GET /schema
- Ensure all required fields present

## 📊 Response Examples

### Health Check
```json
{
  "status": "ok",
  "timestamp": "2025-11-24T10:30:00Z",
  "version": "0.1.0",
  "redis_connected": true
}
```

### ICPMP Result
```json
{
  "schemaVersion": "0.8",
  "recommendations": [
    {
      "requirementId": "REQ_APO_DAY",
      "alternativeRank": 1,
      "configuration": {
        "workPattern": ["D", "D", "D", "D", "O", "O"],
        "employeesRequired": 7,
        "score": 180.0
      },
      "coverage": {
        "expectedCoverageRate": 100.0
      }
    }
  ]
}
```

### Async Job Status
```json
{
  "job_id": "abc123-def456...",
  "status": "completed",
  "created_at": "2025-11-24T10:15:30Z",
  "result": {
    "schemaVersion": "0.6",
    "meta": {...},
    "solution": [...]
  }
}
```

### Queue Stats (Detailed)
```json
{
  "total_jobs": 23,
  "active_jobs": 20,
  "queue_length": 0,
  "workers": 6,
  "jobs": [
    {
      "job_id": "abc123...",
      "status": "completed",
      "created_at": "2025-11-24T10:15:30Z",
      "updated_at": "2025-11-24T10:15:45Z",
      "has_result": true
    }
  ]
}
```

## 🔐 Security Notes

### Admin API Key
- Never commit actual keys to version control
- Rotate keys regularly (every 90 days)
- Use different keys for staging/production
- Keep keys in Postman environment (not collection)

### Production Use
1. Set strong admin_api_key (32+ characters)
2. Test in local environment first
3. Use admin reset only when necessary
4. Monitor logs after admin operations

## 📖 Related Documentation

- **API Documentation**: `/docs` endpoint (Swagger UI)
- **Admin Reset Guide**: `implementation_docs/ADMIN_RESET.md`
- **Quick Reference**: `ADMIN_RESET_QUICKREF.md`
- **Deployment Info**: `implementation_docs/DEPLOYMENT_STATS_RESET.md`

## 🎓 Learning Path

### Beginner
1. Health Check
2. Get Optimal Configurations (ICPMP)
3. Queue Stats

### Intermediate
4. Submit Async Job
5. Get Job Status
6. Delete Job

### Advanced
7. Queue Stats (Detailed)
8. Alternative Input Formats
9. Admin Reset

## 💬 Support

**Issues with Collection:**
- Check environment variables are set
- Verify base_url is correct
- Test Health Check first

**API Questions:**
- Review Swagger docs: `/docs`
- Check implementation guides in `implementation_docs/`

**Feature Requests:**
- Suggest additional test cases
- Request example scenarios

---

**Created:** 2025-11-24
**Version:** 1.0
**Maintained by:** NGRS Solver Team
