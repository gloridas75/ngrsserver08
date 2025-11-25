# 🚀 Postman Quick Start - 5 Minutes

## Step 1: Import (30 seconds)

```
1. Open Postman
2. Click "Import" button (top left)
3. Drag these 3 files:
   ✓ NGRS_Solver_API.postman_collection.json
   ✓ NGRS_Solver_Production.postman_environment.json
   ✓ NGRS_Solver_Local.postman_environment.json
4. Click "Import"
```

## Step 2: Select Environment (10 seconds)

```
Top right corner dropdown: Select "NGRS Solver - Production"
```

## Step 3: Test API (4 minutes)

### Test #1: Is it alive? (20 seconds)
```
1. Expand "Health & Info"
2. Click "Health Check"
3. Click "Send"
4. ✅ Should see: {"status": "ok", "redis_connected": true}
```

### Test #2: Get configurations (30 seconds)
```
1. Expand "Configuration Optimizer (ICPMP)"
2. Click "Get Optimal Configurations"
3. Click "Send"
4. ✅ Should see: 5 alternatives per requirement
```

### Test #3: Submit async job (2 minutes)
```
1. Expand "Asynchronous Solve"
2. Click "Submit Async Job"
3. Click "Send"
4. ✅ Should see: {"job_id": "...", "status": "queued"}
5. Note: job_id automatically saved!

6. Click "Get Job Status"
7. Click "Send" multiple times
8. Watch status: queued → in_progress → completed

9. Once completed: Response includes full solution!
```

### Test #4: Monitor queue (30 seconds)
```
1. Click "Queue Stats (Detailed)"
2. Click "Send"
3. ✅ Should see: All jobs with UUIDs and timestamps
```

### Test #5: Cleanup (30 seconds)
```
1. Click "Delete Job"
2. Click "Send"
3. ✅ Job removed from memory
```

## 🎉 You're Done!

**What you have:**
- ✅ 15 ready-to-use API requests
- ✅ Pre-filled test data
- ✅ Auto-saving job IDs
- ✅ Production + Local environments
- ✅ Admin operations (with authentication)

## 🎯 Next Steps

**Daily Use:**
- Use "Submit Async Job" for real problems
- Monitor with "Queue Stats (Detailed)"
- Clean up with "Delete Job"

**Admin Operations:**
1. Set admin_api_key variable (eye icon, edit)
2. Use "System Reset" for emergency recovery

**Customize:**
- Edit request bodies with your data
- Save responses as examples
- Run entire collection as test suite

## 📚 Full Docs

See `POSTMAN_IMPORT_GUIDE.md` for complete documentation.

---

**Total time:** 5 minutes
**Requests included:** 15
**Environments:** 2
**Auto-features:** job_id tracking, test scripts
