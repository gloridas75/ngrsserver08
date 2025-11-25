# 📦 Postman Collection Files

## Files Available

### 1. Collection
**`NGRS_Solver_API.postman_collection.json`** (17 KB)
- Complete API collection with 15 requests
- Organized into 6 folders
- Pre-filled test data
- Auto-saves job_id for async workflows

### 2. Environments
**`NGRS_Solver_Production.postman_environment.json`** (559 bytes)
- Production endpoint: `https://ngrssolver08.comcentricapps.com`
- Variables: base_url, admin_api_key, job_id

**`NGRS_Solver_Local.postman_environment.json`** (531 bytes)
- Local endpoint: `http://localhost:8080`
- Variables: base_url, admin_api_key, job_id

## 🎯 What's Included

### API Endpoints Covered

| Folder | Requests | Description |
|--------|----------|-------------|
| **Health & Info** | 3 | Health check, version, schema |
| **Configuration Optimizer** | 2 | ICPMP with D-only, N-only, mixed shifts |
| **Synchronous Solve** | 1 | Small problems, immediate results |
| **Asynchronous Solve** | 5 | Submit, status, stats, detailed stats, delete |
| **Admin Operations** | 1 | System reset (API key protected) |
| **Alternative Formats** | 2 | Wrapped and direct input formats |

**Total: 15 pre-configured requests**

### Features

✅ **Auto-tracking**: job_id automatically saved after submission
✅ **Test data**: Every request includes working examples
✅ **Variables**: Switch environments easily
✅ **Authentication**: Admin operations with x-api-key header
✅ **Documentation**: Each request includes description

## 🚀 Quick Import

### Method 1: Drag and Drop
1. Open Postman
2. Click "Import"
3. Drag all 3 JSON files
4. Done!

### Method 2: File Browser
1. Open Postman
2. Click "Import"
3. Click "Choose Files"
4. Select all 3 JSON files
5. Click "Open"

### Method 3: From GitHub
If files are in GitHub repository:
1. Copy raw file URL
2. Postman → Import → Link
3. Paste URL
4. Import

## 📖 Documentation

**Quick Start** (5 minutes):
- `POSTMAN_QUICKSTART.md` - Get started immediately

**Complete Guide** (15 minutes):
- `POSTMAN_IMPORT_GUIDE.md` - Full documentation with examples

## 🎓 Learning Path

### Beginner (5 min)
```
1. Import collection
2. Health Check → Send
3. Get Optimal Configurations → Send
```

### Intermediate (15 min)
```
4. Submit Async Job → Send
5. Get Job Status → Send (repeat)
6. Queue Stats (Detailed) → Send
7. Delete Job → Send
```

### Advanced (30 min)
```
8. Try alternative input formats
9. Test synchronous solve
10. Configure admin_api_key
11. Test admin reset (local first!)
```

## 🔑 Variables Setup

**Required before first use:**
1. Top right: Select "NGRS Solver - Production"
2. Click eye icon 👁️
3. Click "Edit"
4. Update `admin_api_key` if using admin operations
5. Save

**auto_api_key values:**
- Default: `change-me-in-production`
- Update to match server's `ADMIN_API_KEY` environment variable

## 🎬 Example Workflow

### Complete Async Job Flow
```
1. Submit Async Job
   → Returns: {"job_id": "abc-123...", "status": "queued"}
   → Auto-saved to {{job_id}} variable

2. Get Job Status (multiple times)
   → First: {"status": "queued"}
   → Then: {"status": "in_progress"}
   → Finally: {"status": "completed", "result": {...}}

3. Queue Stats (Detailed)
   → See your job in the list with timestamps

4. Delete Job
   → Free memory: {"message": "Job deleted"}
```

## 📊 Test Results

All JSON files validated:
- ✅ Collection JSON: Valid (17 KB)
- ✅ Production environment: Valid (559 bytes)
- ✅ Local environment: Valid (531 bytes)

## 🔍 What Each Request Does

### Health & Info
1. **Health Check** - `GET /health` - Verify API is running
2. **API Version** - `GET /version` - Get version info
3. **Input Schema** - `GET /schema` - JSON schema for validation

### Configuration Optimizer (ICPMP)
4. **Get Optimal Configurations** - `POST /configure` - Top 5 patterns
5. **ICPMP - Mixed Shift Types** - `POST /configure` - Test mixed D+N

### Synchronous Solve
6. **Solve Small Problem** - `POST /solve` - Immediate result

### Asynchronous Solve
7. **Submit Async Job** - `POST /solve/async` - Create job
8. **Get Job Status** - `GET /solve/async/{job_id}` - Check progress
9. **Queue Stats** - `GET /solve/async/stats` - Basic stats
10. **Queue Stats (Detailed)** - `GET /solve/async/stats?details=true` - With UUIDs
11. **Delete Job** - `DELETE /solve/async/{job_id}` - Free memory

### Admin Operations
12. **System Reset** - `POST /admin/reset` - Flush Redis + restart workers

### Alternative Formats
13. **Async - Wrapped Format** - Wrapped: `{"input_json": {...}}`
14. **Async - Direct Format** - Direct NGRS input

## 💡 Pro Tips

### 1. Collections Runner
Run entire collection as test suite:
- Click collection name
- Click "Run"
- Select requests
- Execute

### 2. Save Responses
Right-click request → "Save Response" → "Save as example"

### 3. Environment Switching
Toggle between production and local instantly

### 4. Export Modified Collection
File → Export → Share with team

### 5. Monitor Jobs
Use "Queue Stats (Detailed)" to track all active jobs

## 🐛 Troubleshooting

**Import fails:**
- Check JSON files are not corrupted
- Re-download from source
- Try importing one at a time

**Requests fail:**
- Select correct environment
- Check base_url variable
- Test Health Check first

**Admin reset fails:**
- Update admin_api_key variable
- Check header: x-api-key present
- Verify key matches server

## 🔐 Security

**API Key Storage:**
- ✅ Store in environment (not collection)
- ✅ Mark as "secret" type
- ✅ Never commit actual keys to git
- ✅ Use different keys for staging/production

**Admin Operations:**
- ⚠️ Test in local environment first
- ⚠️ Understand impact (deletes all jobs)
- ⚠️ Requires confirmation in production

## 📞 Support

**Collection Issues:**
- Validate JSON: `python3 -m json.tool <file.json>`
- Check environment selected
- Review variable values (eye icon)

**API Issues:**
- Check `/docs` endpoint (Swagger UI)
- Review API logs
- Test with curl first

## 🎉 You're Ready!

You now have:
- ✅ Complete API collection
- ✅ Production + Local environments
- ✅ 15 ready-to-use requests
- ✅ Auto-tracking job IDs
- ✅ Test data included
- ✅ Documentation

**Start testing:** `POSTMAN_QUICKSTART.md`

---

**Created:** 2025-11-24
**Format:** Postman Collection v2.1.0
**Requests:** 15
**Environments:** 2
