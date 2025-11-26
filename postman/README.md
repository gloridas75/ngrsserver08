# NGRS Solver API - Postman Collection

This folder contains Postman collection and environment files for testing the NGRS Solver API.

## Files

- **NGRS_Solver_API.postman_collection.json** - Complete API collection with all endpoints
- **NGRS_Solver_Local.postman_environment.json** - Environment for local testing
- **NGRS_Solver_Production.postman_environment.json** - Environment for production server

## 🆕 Latest Updates (v0.7.2 - Nov 26, 2025)

### New Features Added

#### 1. **Webhook Notifications** 🔔
Automatically receive HTTP POST notification when jobs complete - no more polling!

**How to Use:**
```json
{
  "webhook_url": "https://webhook.site/your-unique-url",
  "input_json": { ... }
}
```

**Webhook Payload (sent on completion):**
```json
{
  "job_id": "abc-123-def-456",
  "status": "COMPLETED",
  "timestamp": "2025-11-26T14:30:15.123456",
  "message": "Job completed successfully"
}
```

**Test Setup:**
1. Get free webhook URL from https://webhook.site
2. Use "Submit with Webhook" request
3. Watch webhook.site for instant notification

**Status Values:** `COMPLETED`, `FAILED`, `CANCELLED`

---

#### 2. **Quick Feasibility Pre-Check** ⚡
Fast validation (<100ms) before queuing expensive solver jobs.

**Automatic Checks:**
- Employee count estimation
- Role/rank/gender/scheme matching
- Work pattern feasibility
- MOM constraint violations

**Response includes `feasibility_check`:**
```json
{
  "job_id": "abc-123",
  "feasibility_check": {
    "is_feasible": false,
    "summary": "Insufficient employees",
    "warnings": [
      "Need 15-18 employees, only 5 available",
      "No Scheme B employees for night shifts"
    ],
    "recommendations": [
      "Add 10-13 more Scheme A/B employees",
      "Consider hybrid work patterns"
    ],
    "details": [...]
  }
}
```

**Benefits:**
- Catch problems before 10-minute solver runs
- Get actionable recommendations
- Save compute resources

---

#### 3. **Job Cancellation** 🛑
Stop queued or running jobs gracefully.

**Two Endpoints:**
- `DELETE /solve/async/{job_id}` - Standard RESTful
- `POST /solve/async/{job_id}/cancel` - Alternative for systems blocking DELETE

**Cancellation Strategies:**

| Job Status | Action | Time |
|------------|--------|------|
| QUEUED | Remove from queue immediately | Instant |
| IN_PROGRESS | Set cancellation flag, worker stops at checkpoint | 30-60s |
| COMPLETED/FAILED | Delete result, mark as cancelled | Instant |

**Response:**
```json
{
  "message": "Job removed from queue",
  "job_id": "abc-123",
  "previous_status": "QUEUED",
  "new_status": "CANCELLED"
}
```

**Use Cases:**
- Stop expensive runs with wrong input
- Clean up completed jobs
- Free up queue slots
- Cancel jobs taking too long

**Note:** CP-SAT solver cannot be interrupted mid-execution, so IN_PROGRESS jobs complete their current iteration first.

---

#### 4. **ISO Timestamps** 📅
Human-readable timestamps in all responses.

**Before:**
```json
{
  "created_at": 1732611015.123456,  // ❌ Unix epoch
  "updated_at": 1732611125.654321
}
```

**After:**
```json
{
  "created_at": "2025-11-26T14:30:15.123456",  // ✅ ISO 8601
  "updated_at": "2025-11-26T14:32:05.654321"
}
```

**Benefits:**
- Easy to read and compare
- Sortable alphabetically
- Includes microseconds for precision
- No timezone conversion needed (always UTC)

---

#### 5. **Automatic Job Cleanup** 🧹
Jobs and results automatically expire after 1 hour (TTL).

**Before:**
- Jobs persisted forever
- Manual deletion required
- Redis memory filled up

**After:**
- Jobs expire after 3600 seconds
- Automatic cleanup
- No manual maintenance needed

**Impact:**
- Reduced Redis memory usage
- No stale jobs
- Better performance

---

#### 6. **CP-SAT Parallelization** 🚀
Multi-threaded search for 2-3x faster solving on large problems.

**Automatic Thread Allocation:**

| Problem Size | Variables | Threads |
|--------------|-----------|---------|
| Small | <5,000 | 1 |
| Medium | 5-20K | 2 |
| Large | 20-150K | 4-8 |
| Very Large | >150K | 16 |

**Manual Override:**
Set environment variable `CPSAT_NUM_THREADS=8` to force specific thread count.

**Solver Output:**
```
[solve] Running CP-SAT solver...
  Problem size: 880 slots × 50 employees
  Time limit: 40s (adaptive)
  Parallel search workers: 8 (adaptive)  ⬅️ NEW
```

**Benefits:**
- Faster solving for large rosters
- Better search space exploration
- No changes to input/output formats
- Fully backward compatible

---

## Recent Updates (v0.7.1 - Nov 25, 2025)

### ICPMP Configuration Optimizer - Schema Changes

#### 1. Shift-Specific Headcount (`headcountPerShift`)

The `/configure` endpoint now uses **`headcountPerShift`** instead of `headcountPerDay` for more precise shift coverage specification.

##### Old Schema (Deprecated)
```json
{
  "requirements": [
    {
      "shiftTypes": ["D", "N"],
      "headcountPerDay": 50  // ❌ Ambiguous
    }
  ]
}
```

##### New Schema (Required)
```json
{
  "requirements": [
    {
      "shiftTypes": ["D", "N"],
      "headcountPerShift": {
        "D": 25,  // ✅ Clear: 25 for Day shift
        "N": 25   // ✅ Clear: 25 for Night shift
      }
    }
  ]
}
```

#### 2. Shift Hour Definitions (`shiftDefinitions`)

**NEW**: You can now specify custom shift hours for accurate calculations. This is especially important for:
- Scheme P shifts (8-hour shifts)
- Non-standard shift durations
- Mixed shift types with different hours

##### Default Behavior (Without shiftDefinitions)
If not provided, all shifts default to **11.0 net hours** (12 gross - 1 lunch):

```json
{
  "requirements": [{"shiftTypes": ["D"], "headcountPerShift": {"D": 4}}],
  "constraints": {"maxWeeklyNormalHours": 44}
}
// D shift assumes 11.0 hours
```

##### Custom Shift Hours (With shiftDefinitions)
For accurate calculations with 8-hour Scheme P shifts:

```json
{
  "shiftDefinitions": {
    "W": {
      "grossHours": 8.0,
      "lunchBreak": 1.0,
      "description": "Wing shift (8h gross, 7h net)"
    },
    "E": {
      "grossHours": 8.0,
      "lunchBreak": 1.0,
      "description": "Evening shift (8h gross, 7h net)"
    }
  },
  "requirements": [
    {
      "shiftTypes": ["W", "E"],
      "headcountPerShift": {"W": 2, "E": 1}
    }
  ]
}
```

##### Comparing 12-Hour vs 8-Hour Shifts
```json
{
  "shiftDefinitions": {
    "D": {"grossHours": 12.0, "lunchBreak": 1.0},  // 11h net
    "P": {"grossHours": 8.0, "lunchBreak": 1.0}    // 7h net
  },
  "requirements": [
    {"id": "REQ_12H", "shiftTypes": ["D"], "headcountPerShift": {"D": 4}},
    {"id": "REQ_8H", "shiftTypes": ["P"], "headcountPerShift": {"P": 4}}
  ]
}
```

**Why this matters**: With `maxWeeklyNormalHours: 44`:
- 12-hour shifts: ~4 days/week → fewer employees needed
- 8-hour shifts: ~5.5 days/week → more employees needed for same coverage

### Response Changes

The API now returns per-shift details:

```json
{
  "configuration": {
    "employeesRequired": 175,
    "employeesRequiredPerShift": {
      "D": 88,
      "N": 87
    }
  },
  "coverage": {
    "requiredPerShift": {
      "D": 25,
      "N": 25
    },
    "requiredPerDay": 50
  }
}
```

## How to Import Updated Collection

### Option 1: Replace Entire Collection (Recommended)

1. **Delete Old Collection** (if exists):
   - In Postman, right-click "NGRS Solver API" collection
   - Select "Delete"
   - Confirm deletion

2. **Import New Collection**:
   - Click "Import" button (top left)
   - Drag `NGRS_Solver_API.postman_collection.json` or click "Choose Files"
   - Click "Import"

3. **Verify Import**:
   - Expand "Configuration Optimizer (ICPMP)" folder
   - Open "Get Optimal Configurations" request
   - Check request body uses `headcountPerShift`

### Option 2: Update Existing Requests Manually

If you have custom modifications you want to keep:

1. **Open Each ICPMP Request**:
   - "Get Optimal Configurations"
   - "ICPMP - Mixed Shift Types"

2. **Update Request Body**:
   - Find `"headcountPerDay": <number>` in each requirement
   - Replace with:
     ```json
     "headcountPerShift": {
       "D": <day_count>,
       "N": <night_count>
     }
     ```
   
3. **Remove Deprecated Fields** (if present):
   - Remove `"shifts": [...]` array (no longer needed)
   - Remove `"optimizationGoals"` (no longer used)

### Option 3: Import as New Collection (Side-by-Side)

If you want to keep both old and new:

1. **Rename Old Collection**:
   - Right-click "NGRS Solver API" → Rename
   - Change to "NGRS Solver API (OLD)"

2. **Import New Collection**:
   - Follow steps in Option 1
   - Both collections will coexist

## Environment Setup

### Local Development

1. Import `NGRS_Solver_Local.postman_environment.json`
2. Set as active environment (top-right dropdown)
3. Variables:
   - `base_url`: http://localhost:8000
   - `admin_api_key`: your-local-key

### Production

1. Import `NGRS_Solver_Production.postman_environment.json`
2. Set as active environment
3. Variables:
   - `base_url`: https://ngrssolver08.comcentricapps.com
   - `admin_api_key`: (set your production key)

## Testing the New Schema

### Quick Test - Day Shift Only

1. Open "Get Optimal Configurations" request
2. Verify body has:
   ```json
   {
     "requirements": [
       {
         "id": "REQ_APO_DAY",
         "shiftTypes": ["D"],
         "headcountPerShift": {
           "D": 4
         }
       }
     ]
   }
   ```
3. Click "Send"
4. Check response includes:
   - `configuration.employeesRequiredPerShift.D`
   - `coverage.requiredPerShift.D`

### Quick Test - Mixed Shifts

1. Open "ICPMP - Mixed Shift Types" request
2. Verify body has:
   ```json
   {
     "requirements": [
       {
         "shiftTypes": ["D", "N"],
         "headcountPerShift": {
           "D": 25,
           "N": 25
         }
       }
     ]
   }
   ```
3. Click "Send"
4. Check response shows both D and N in `employeesRequiredPerShift`

## Collection Structure

```
NGRS Solver API/
├── Health & Info/
│   ├── Health Check
│   ├── API Version
│   └── Input Schema
├── Configuration Optimizer (ICPMP)/
│   ├── Get Optimal Configurations
│   └── ICPMP - Mixed Shift Types
├── Synchronous Solve/
│   └── Solve Small Problem
├── Asynchronous Solve/                         ⭐ ENHANCED
│   ├── Submit Async Job                        ⭐ UPDATED: Feasibility check
│   ├── Submit with Webhook                     🆕 NEW: Webhook notifications
│   ├── Get Job Status                          ⭐ UPDATED: ISO timestamps
│   ├── Cancel Job (DELETE)                     🆕 NEW: Smart cancellation
│   ├── Cancel Job (POST)                       🆕 NEW: Alternative endpoint
│   ├── Queue Stats                             ⭐ UPDATED: CANCELLED status
│   ├── Queue Stats (Detailed)                  ⭐ UPDATED: ISO timestamps
│   └── Delete Job                              ⚠️  DEPRECATED
├── Admin Operations/
│   └── System Reset
└── Alternative Input Formats/
    ├── Async - Wrapped Format
    └── Async - Direct Format
```

## Example Requests

### Single Shift Type (Day Only)
```json
{
  "planningHorizon": {
    "startDate": "2025-12-01",
    "endDate": "2025-12-31"
  },
  "requirements": [
    {
      "id": "REQ_DAY",
      "shiftTypes": ["D"],
      "headcountPerShift": {"D": 5}
    }
  ],
  "constraints": {
    "maxWeeklyNormalHours": 44
  }
}
```

### Multiple Shift Types (Day + Night)
```json
{
  "planningHorizon": {
    "startDate": "2025-12-01",
    "endDate": "2025-12-31"
  },
  "requirements": [
    {
      "id": "REQ_MIXED",
      "shiftTypes": ["D", "N"],
      "headcountPerShift": {
        "D": 10,
        "N": 5
      }
    }
  ],
  "constraints": {
    "maxWeeklyNormalHours": 44
  }
}
```

## Troubleshooting

### Error: "headcountPerShift is required"

**Cause**: Using old schema with `headcountPerDay`

**Solution**: Update request body to use `headcountPerShift` as shown above

### Error: "shifts must be defined for all shiftTypes"

**Cause**: `headcountPerShift` doesn't include all shift types from `shiftTypes`

**Solution**: Ensure every shift type in `shiftTypes` has an entry in `headcountPerShift`

Example:
```json
{
  "shiftTypes": ["D", "N"],
  "headcountPerShift": {
    "D": 10,
    "N": 5
  }
}
```

## Support

For issues or questions:
- Check API documentation: `{{base_url}}/docs`
- Review schema: `{{base_url}}/schema`
- Contact: support@comcentricapps.com

## Version History

- **v0.7.2** (Nov 26, 2025) - Added webhook notifications, feasibility pre-check, job cancellation, ISO timestamps, auto-cleanup (TTL), CP-SAT parallelization
- **v0.7.1** (Nov 25, 2025) - Added `headcountPerShift` schema, per-shift output details
- **v0.7.0** (Nov 15, 2025) - ICPMP improvements, top 5 patterns, 100+ employees support
- **v0.6.0** (Oct 2025) - Redis async mode, job management
- **v0.5.0** (Sep 2025) - Initial ICPMP configuration optimizer

---

## Quick Start Guide

### 1. Import Collection
- Delete old "NGRS Solver API" collection (if exists)
- Import `NGRS_Solver_API.postman_collection.json`
- Import environment file (Local or Production)

### 2. Test New Features

**Webhook Notification:**
```
1. Visit https://webhook.site - copy your unique URL
2. Open "Submit with Webhook" request
3. Replace webhook_url with your URL
4. Send request
5. Watch webhook.site for completion notification
```

**Feasibility Check:**
```
1. Open "Submit Async Job" request
2. Send request
3. Check response for "feasibility_check" field
4. Review warnings/recommendations before solving
```

**Job Cancellation:**
```
1. Submit a job (save job_id)
2. Open "Cancel Job (DELETE)" request
3. Send request
4. Job stops/removed within 30-60 seconds
```

### 3. Monitor Jobs

**Basic Stats:**
```
GET {{base_url}}/solve/async/stats
```

**Detailed View with ISO Timestamps:**
```
GET {{base_url}}/solve/async/stats?details=true
```

---

## Breaking Changes

None! All new features are:
- ✅ Backward compatible
- ✅ Optional (webhook_url is optional)
- ✅ Additive (new fields in responses)
- ✅ No input format changes

Existing integrations continue to work without modifications.

---