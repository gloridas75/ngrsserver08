# NGRS Solver API - Postman Collection

This folder contains Postman collection and environment files for testing the NGRS Solver API.

## Files

- **NGRS_Solver_API.postman_collection.json** - Complete API collection with all endpoints
- **NGRS_Solver_Local.postman_environment.json** - Environment for local testing
- **NGRS_Solver_Production.postman_environment.json** - Environment for production server
- **PATTERN_BASED_EXAMPLES.md** - 📘 Ready-to-use JSON examples for pattern-based scheduling

## Quick Links

- [Pattern-Based Examples](./PATTERN_BASED_EXAMPLES.md) - Complete request examples with balanceWorkload and minimizeEmployeeCount modes
- [API Documentation](#optimization-modes-balanceworkload-vs-minimizeemployeecount) - Optimization mode guidance
- [Troubleshooting Guide](#troubleshooting-infeasible-results) - Common issues and solutions

## 🆕 Latest Updates (v0.7.3 - Jan 12, 2025)

### Pattern-Based Scheduling & Optimization Modes 🎯

#### 1. **Optimization Modes: balanceWorkload vs minimizeEmployeeCount**

Choose the right optimization strategy for your scheduling needs:

##### **balanceWorkload** (Recommended for Patterns) ✅

**When to Use:**
- Rotation-based schedules with work patterns (D-D-N-N-O-O, D-D-D-D-O-O, etc.)
- Need consistent employee utilization
- Want fair workload distribution
- Pattern-based continuous coverage

**How It Works:**
- Distributes assignments evenly across employees
- Minimizes the gap between most-worked and least-worked employees
- Naturally achieves minimal employee count through pattern constraints
- Works seamlessly with continuous adherence behavior

**Expected Results:**
- 100% employee utilization
- 20-21 shifts per employee per month (for 6-day patterns)
- No under-utilized employees (no 1-2 shift assignments)
- OPTIMAL status with proper offset distribution

**Input Example:**
```json
{
  "optimizationMode": "balanceWorkload",
  "fixedRotationOffset": true,
  "employees": [
    {"employeeId": "E001", "rotationOffset": 0, ...},
    {"employeeId": "E002", "rotationOffset": 1, ...},
    {"employeeId": "E003", "rotationOffset": 2, ...}
  ]
}
```

---

##### **minimizeEmployeeCount** ⚠️

**When to Use:**
- Simple shift coverage without rotation patterns
- Need absolute minimum employee count
- One-off or irregular scheduling
- No pattern-based constraints

**⚠️ WARNING - Pattern Compatibility:**
- **100,000× weight penalty** on employee count overwhelms other constraints
- Can cause offset clustering (all employees on same offset)
- May produce INFEASIBLE results with pattern-based rotation
- Conflicts with continuous adherence for patterns
- Under-utilization possible (employees with 1-2 shifts only)

**How It Works:**
- Aggressively minimizes total number of employees used
- Priority: Employee count > Pattern adherence > Coverage quality
- Can sacrifice workload balance for lower headcount

**Use Cases:**
- Emergency staffing with limited workforce
- Budget-constrained simple shift assignments
- Non-rotating shift coverage

**Limitations:**
❌ Not recommended for D-D-N-N-O-O or multi-day patterns  
❌ May create coverage gaps with rotation offsets  
❌ Can violate continuous adherence expectations  
❌ Results may be non-deterministic

---

#### 2. **Fixed Rotation Offsets** 🔄

**Parameter:** `fixedRotationOffset` (boolean)

**Purpose:** Prevents solver from re-clustering employees on the same rotation offset, which can create coverage gaps in pattern-based schedules.

**When to Use:**
- ✅ Always use with pattern-based rotation (D-D-N-N-O-O, etc.)
- ✅ Required for continuous adherence behavior
- ✅ When employees have pre-assigned offsets

**How to Configure:**

1. **Set fixedRotationOffset to true:**
```json
{
  "fixedRotationOffset": true
}
```

2. **Pre-distribute employee offsets (0-5 for 6-day pattern):**
```json
{
  "employees": [
    {"employeeId": "E001", "rotationOffset": 0},
    {"employeeId": "E002", "rotationOffset": 1},
    {"employeeId": "E003", "rotationOffset": 2},
    {"employeeId": "E004", "rotationOffset": 3},
    {"employeeId": "E005", "rotationOffset": 4},
    {"employeeId": "E006", "rotationOffset": 5},
    {"employeeId": "E007", "rotationOffset": 0},  // Round-robin
    {"employeeId": "E008", "rotationOffset": 1}
  ]
}
```

**Offset Distribution Strategy:**
- For 6-day pattern (D-D-N-N-O-O): Use offsets 0-5
- Distribute employees round-robin across all offsets
- Ensures at least 1 employee per offset for coverage diversity
- Prevents all employees working same days

**Without Fixed Offsets (❌ Not Recommended):**
- Solver may cluster employees on offset 2 or 3
- Creates gaps in coverage on other days
- Can cause INFEASIBLE results
- Unpredictable behavior

---

#### 3. **Continuous Adherence Behavior** 📊

**What It Does:**
When an employee is selected for a work pattern, they are assigned to work **ALL** days in their pattern cycle.

**Impact:**
- Employee works full pattern (~20 shifts/month for D-D-N-N-O-O)
- No partial utilization (no 1-2 shift assignments)
- Predictable workload for employees
- Better schedule consistency

**Example Pattern: D-D-N-N-O-O**
- Pattern repeats every 6 days
- Employee works 4 days, off 2 days per cycle
- Over 30-day month: ~20 shifts per employee
- Each shift assignment = full pattern commitment

**Utilization Metrics:**
- **100% Utilization:** All selected employees work full patterns
- **Efficiency:** 100.0-100.2% (20-21 shifts per employee)
- **Coverage:** All slots filled with proper offset distribution

---

#### 4. **Troubleshooting INFEASIBLE Results** 🔧

Common issues and solutions:

##### **Problem: Solver returns INFEASIBLE**

**Possible Causes:**

1. **Insufficient employees for pattern coverage**
   - **Solution:** Increase employee count or reduce demand
   - **Check:** Need ~3-5 employees per offset (0-5) for D-D-N-N-O-O pattern

2. **Offset clustering (all employees same offset)**
   - **Solution:** Set `fixedRotationOffset: true` and pre-distribute offsets
   - **Check:** Each offset (0-5) should have at least 1-2 employees

3. **minimizeEmployeeCount mode with patterns**
   - **Solution:** Switch to `optimizationMode: "balanceWorkload"`
   - **Reason:** 100,000× weight causes offset clustering

4. **Conflicting constraints (gender, role, scheme)**
   - **Solution:** Review whitelist/blacklist, gender requirements, qualifications
   - **Check:** Feasibility check warnings

5. **Pattern-constraint conflicts**
   - **Solution:** Verify pattern length matches demand cycle
   - **Check:** D-D-N-N-O-O (6 days) requires 6-day rotation cycle

##### **Problem: Low employee utilization (many employees with 1-2 shifts)**

**Cause:** minimizeEmployeeCount mode without continuous adherence

**Solution:**
1. Switch to `optimizationMode: "balanceWorkload"`
2. Enable `fixedRotationOffset: true`
3. Pre-distribute employee offsets

**Expected After Fix:**
- 20-21 shifts per employee (for D-D-N-N-O-O)
- 100% utilization rate
- No employees with <15 shifts

##### **Problem: Non-deterministic results (different output each run)**

**Cause:** Solver exploring different offset assignments

**Solution:**
1. Set `fixedRotationOffset: true`
2. Pre-assign employee rotation offsets in input JSON
3. Use `balanceWorkload` mode for consistency

---

#### 5. **Best Practices Summary** 📋

**For Pattern-Based Rotation Schedules:**

```json
{
  "optimizationMode": "balanceWorkload",  // ✅ Recommended
  "fixedRotationOffset": true,             // ✅ Required
  "employees": [
    {"employeeId": "E001", "rotationOffset": 0},  // Pre-distribute
    {"employeeId": "E002", "rotationOffset": 1},
    {"employeeId": "E003", "rotationOffset": 2},
    {"employeeId": "E004", "rotationOffset": 3},
    {"employeeId": "E005", "rotationOffset": 4},
    {"employeeId": "E006", "rotationOffset": 5}
  ],
  "demandItems": [{
    "shifts": [{
      "rotationSequence": ["D", "D", "N", "N", "O", "O"],
      "coverageAnchor": "2025-01-01"
    }]
  }]
}
```

**Expected Results:**
- Status: OPTIMAL
- Utilization: 100%
- Shifts per employee: 20-21 per month
- Solve time: 10-30 seconds (for 50-100 employees)

**For Simple Shift Coverage (No Patterns):**

```json
{
  "optimizationMode": "minimizeEmployeeCount",  // OK for simple coverage
  "fixedRotationOffset": false,                  // Not needed
  "employees": [...],  // No rotationOffset required
  "demandItems": [{
    "shifts": [{
      // No rotationSequence
    }]
  }]
}
```

---

## Previous Updates (v0.7.2 - Nov 26, 2025)

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