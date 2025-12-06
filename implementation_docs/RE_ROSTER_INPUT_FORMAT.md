# Re-Roster (Incremental Solve) Input Format

## Overview

The **Incremental Solver** (also called "Re-Roster") allows you to adjust a roster mid-month when changes occur (new employees, departures, long leave) **without disturbing already-committed assignments**. It solves only the unassigned/affected slots while keeping locked assignments intact.

**Implementation Status:** ✅ **FULLY IMPLEMENTED** (v0.80)

---

## When to Use Re-Roster

Use incremental solve when:
1. **New employee joins** mid-month → Add them to unassigned slots
2. **Employee departs/resigns** → Free up their assignments, reassign to others
3. **Employee goes on long leave** → Temporarily free up assignments
4. **Manual changes required** → Lock confirmed assignments, re-solve the rest

---

## API Endpoint

```
POST /solve/incremental
Content-Type: application/json
```

---

## Input JSON Format

### Complete Structure

```json
{
  "schemaVersion": "0.80",
  "planningReference": "DEC2025_ROSTER_v2",
  
  "temporalWindow": {
    "cutoffDate": "2025-12-15",
    "solveFromDate": "2025-12-16",
    "solveToDate": "2025-12-31"
  },
  
  "previousOutput": {
    "schemaVersion": "0.95",
    "planningReference": "DEC2025_ROSTER_v1",
    "solverRun": { ... },
    "score": { ... },
    "assignments": [ ... ]
  },
  
  "employeeChanges": {
    "newJoiners": [
      {
        "employee": {
          "employeeId": "NEW12345",
          "firstName": "John",
          "lastName": "Doe",
          "rankId": "SER",
          "productTypes": ["APO"],
          "workPattern": ["D", "D", "D", "D", "O", "D", "D"],
          "rotationOffset": 0,
          "contractedHours": 176.0
        },
        "availableFrom": "2025-12-16"
      }
    ],
    
    "notAvailableFrom": [
      {
        "employeeId": "EMP00567",
        "notAvailableFrom": "2025-12-20"
      }
    ],
    
    "longLeave": [
      {
        "employeeId": "EMP00890",
        "leaveFrom": "2025-12-18",
        "leaveTo": "2025-12-22"
      }
    ]
  },
  
  "demandItems": [ ... ],
  "planningHorizon": { ... },
  "solverConfig": { ... }
}
```

---

## Field Descriptions

### 1. `schemaVersion` (required)
**Type:** `string`  
**Value:** `"0.80"`  
**Description:** Schema version for incremental solve.

---

### 2. `planningReference` (required)
**Type:** `string`  
**Example:** `"DEC2025_ROSTER_v2"`  
**Description:** Reference ID for this planning iteration.

---

### 3. `temporalWindow` (required)
**Type:** `object`  
**Description:** Defines which dates to lock vs which to solve.

#### Fields:
- **`cutoffDate`** (required): Lock all assignments **before** this date (exclusive)
  - Format: `"YYYY-MM-DD"`
  - Example: `"2025-12-15"`
  - Assignments on or before this date are **locked** and won't be changed

- **`solveFromDate`** (required): Start solving **from** this date (inclusive)
  - Format: `"YYYY-MM-DD"`
  - Example: `"2025-12-16"`
  - Must be **greater than** `cutoffDate`

- **`solveToDate`** (required): End of planning horizon (inclusive)
  - Format: `"YYYY-MM-DD"`
  - Example: `"2025-12-31"`
  - Must be **greater than or equal to** `solveFromDate`

**Validation:**
```
cutoffDate < solveFromDate <= solveToDate
```

**Example Timeline:**
```
Dec 1-15:  LOCKED (cutoffDate = Dec 15)
Dec 16-31: SOLVABLE (solveFromDate = Dec 16, solveToDate = Dec 31)
```

---

### 4. `previousOutput` (required)
**Type:** `object`  
**Description:** The **complete output JSON** from the previous solve run.

#### Required Fields:
- `schemaVersion`: Previous schema version (e.g., `"0.95"`)
- `planningReference`: Previous planning reference
- `solverRun`: Solver execution metadata
- `score`: Score from previous solve
- `assignments`: **Critical** - Array of all assignments from previous solve

#### Example:
```json
{
  "schemaVersion": "0.95",
  "planningReference": "DEC2025_ROSTER_v1",
  "solverRun": {
    "runId": "SRN-20251201-180000",
    "solverVersion": "optSolve-py-0.95.0",
    "status": "OPTIMAL",
    "durationSeconds": 45.3
  },
  "score": {
    "overall": 950,
    "hard": 0,
    "soft": 50
  },
  "assignments": [
    {
      "assignmentId": "ASN-001",
      "demandId": "DI-001",
      "date": "2025-12-01",
      "shiftCode": "D",
      "employeeId": "EMP001",
      "status": "ASSIGNED",
      "startDateTime": "2025-12-01T09:00:00",
      "endDateTime": "2025-12-01T18:00:00",
      "hours": {
        "gross": 9,
        "lunch": 1,
        "normal": 8,
        "ot": 0,
        "paid": 9
      }
    }
    // ... more assignments
  ]
}
```

**💡 Tip:** Use the output from your initial solve as `previousOutput`.

---

### 5. `employeeChanges` (required)
**Type:** `object`  
**Description:** Changes to the employee pool.

#### 5.1 `newJoiners` (optional)
**Type:** `array`  
**Description:** New employees joining mid-month.

Each item:
```json
{
  "employee": {
    "employeeId": "NEW12345",
    "firstName": "John",
    "lastName": "Doe",
    "rankId": "SER",
    "productTypes": ["APO"],
    "workPattern": ["D", "D", "D", "D", "O", "D", "D"],
    "rotationOffset": 0,
    "contractedHours": 176.0,
    "availability": []  // Optional
  },
  "availableFrom": "2025-12-16"
}
```

**Fields:**
- `employee`: Full employee object (same format as regular solve input)
- `availableFrom`: Date they can start working (YYYY-MM-DD)

---

#### 5.2 `notAvailableFrom` (optional)
**Type:** `array`  
**Description:** Employees who departed or resigned.

Each item:
```json
{
  "employeeId": "EMP00567",
  "notAvailableFrom": "2025-12-20"
}
```

**Behavior:**
- All assignments **from this date onwards** will be freed
- Assignments **before** this date remain locked (if before cutoffDate)
- Freed slots become available for reassignment

---

#### 5.3 `longLeave` (optional)
**Type:** `array`  
**Description:** Employees on temporary leave.

Each item:
```json
{
  "employeeId": "EMP00890",
  "leaveFrom": "2025-12-18",
  "leaveTo": "2025-12-22"
}
```

**Behavior:**
- Assignments within this date range are freed
- Employee becomes available again after `leaveTo`
- Freed slots reassigned to other employees

---

### 6. `demandItems` (required)
**Type:** `array`  
**Description:** Same as regular solve - full demand specification.

**💡 Tip:** Use the same `demandItems` from your original solve.

---

### 7. `planningHorizon` (required)
**Type:** `object`  
**Description:** Planning horizon metadata.

```json
{
  "startDate": "2025-12-01",
  "endDate": "2025-12-31",
  "lengthDays": 31
}
```

---

### 8. `solverConfig` (optional)
**Type:** `object`  
**Description:** Solver configuration overrides.

```json
{
  "timeLimitSeconds": 120,
  "optimizationLevel": "OPTIMAL"
}
```

---

## Output Format

The incremental solve returns a **complete roster** with:
1. **Locked assignments** (from previous solve) - marked with `"source": "locked"`
2. **New assignments** (from incremental solve) - marked with `"source": "incremental"`

### Output Structure

```json
{
  "schemaVersion": "0.95",
  "planningReference": "DEC2025_ROSTER_v2",
  
  "solverRun": {
    "runId": "SRN-20251216-100000",
    "status": "OPTIMAL",
    "durationSeconds": 28.5
  },
  
  "assignments": [
    {
      // Locked assignment (before cutoffDate)
      "date": "2025-12-10",
      "employeeId": "EMP001",
      "status": "ASSIGNED",
      "auditInfo": {
        "solverRunId": "SRN-20251201-180000",
        "source": "locked",
        "timestamp": "2025-12-01T18:00:00",
        "previousJobId": "abc-123"
      }
    },
    {
      // New assignment (from incremental solve)
      "date": "2025-12-20",
      "employeeId": "NEW12345",
      "status": "ASSIGNED",
      "auditInfo": {
        "solverRunId": "SRN-20251216-100000",
        "source": "incremental",
        "timestamp": "2025-12-16T10:00:00"
      }
    }
  ],
  
  "incrementalSolve": {
    "cutoffDate": "2025-12-15",
    "solveFromDate": "2025-12-16",
    "lockedCount": 385,
    "freedDepartedCount": 15,
    "freedLeaveCount": 8,
    "solvableCount": 297,
    "newJoinerCount": 1
  }
}
```

---

## Use Case Examples

### Example 1: New Employee Joins Mid-Month

**Scenario:** New employee joins on Dec 16, need to assign unassigned slots.

```json
{
  "schemaVersion": "0.80",
  "planningReference": "DEC2025_NEW_JOINER",
  "temporalWindow": {
    "cutoffDate": "2025-12-15",
    "solveFromDate": "2025-12-16",
    "solveToDate": "2025-12-31"
  },
  "previousOutput": { /* Load from initial solve output */ },
  "employeeChanges": {
    "newJoiners": [
      {
        "employee": {
          "employeeId": "NEW001",
          "firstName": "Sarah",
          "lastName": "Smith",
          "rankId": "SER",
          "productTypes": ["APO"],
          "workPattern": ["D", "D", "D", "D", "O", "D", "D"],
          "rotationOffset": 0,
          "contractedHours": 176.0
        },
        "availableFrom": "2025-12-16"
      }
    ],
    "notAvailableFrom": [],
    "longLeave": []
  },
  "demandItems": [ /* Same as original */ ],
  "planningHorizon": {
    "startDate": "2025-12-01",
    "endDate": "2025-12-31",
    "lengthDays": 31
  }
}
```

**Result:**
- Dec 1-15: **Locked** (all assignments preserved)
- Dec 16-31: **Re-solved** with new employee included
- Unassigned slots now filled with new employee

---

### Example 2: Employee Departs Mid-Month

**Scenario:** Employee EMP567 resigns effective Dec 20.

```json
{
  "temporalWindow": {
    "cutoffDate": "2025-12-15",
    "solveFromDate": "2025-12-16",
    "solveToDate": "2025-12-31"
  },
  "employeeChanges": {
    "newJoiners": [],
    "notAvailableFrom": [
      {
        "employeeId": "EMP567",
        "notAvailableFrom": "2025-12-20"
      }
    ],
    "longLeave": []
  }
}
```

**Result:**
- Dec 1-15: **Locked** (including EMP567's assignments)
- Dec 16-19: **Locked** (EMP567's assignments kept)
- Dec 20-31: **Freed** (EMP567's assignments released, reassigned to others)

---

### Example 3: Employee on Long Leave

**Scenario:** Employee EMP890 on leave Dec 18-22.

```json
{
  "temporalWindow": {
    "cutoffDate": "2025-12-15",
    "solveFromDate": "2025-12-16",
    "solveToDate": "2025-12-31"
  },
  "employeeChanges": {
    "newJoiners": [],
    "notAvailableFrom": [],
    "longLeave": [
      {
        "employeeId": "EMP890",
        "leaveFrom": "2025-12-18",
        "leaveTo": "2025-12-22"
      }
    ]
  }
}
```

**Result:**
- Dec 1-17: **Locked** (EMP890's assignments preserved)
- Dec 18-22: **Freed** (EMP890's assignments released, reassigned)
- Dec 23-31: **Re-solved** (EMP890 available again)

---

## How It Works Internally

1. **Classification Phase:**
   - Reads `previousOutput.assignments`
   - Classifies assignments as LOCKED (before cutoffDate) or SOLVABLE (from solveFromDate)
   - Identifies freed slots from departures/leave

2. **Employee Pool Merge:**
   - Starts with previous employees
   - Adds `newJoiners`
   - Removes `notAvailableFrom` employees (after their departure date)
   - Marks `longLeave` employees as unavailable during leave period

3. **Constraint Context:**
   - Calculates locked weekly hours (C2 constraint)
   - Tracks locked consecutive days (C3 constraint)
   - Passes context to solver engine via `ctx['_incremental']`

4. **Solving:**
   - Builds model ONLY for solvable slots
   - Respects all constraints with locked context
   - Generates new assignments

5. **Output Merge:**
   - Combines locked + new assignments
   - Adds audit trail to each assignment
   - Includes `incrementalSolve` metadata

---

## API Testing

### Using curl

```bash
curl -X POST "https://ngrssolver08.comcentricapps.com/solve/incremental" \
  -H "Content-Type: application/json" \
  -d @input/incremental/my_reroster_request.json \
  -o output/incremental_result.json
```

### Using Postman

1. Import collection: `postman/NGRS_Solver_API.postman_collection.json`
2. Find: **"Incremental Solve - New Joiner"** request
3. Update body with your data
4. Send request

---

## Validation Rules

The solver validates:

1. **Temporal Window:**
   - ✓ `cutoffDate < solveFromDate <= solveToDate`
   - ✓ Dates are valid (YYYY-MM-DD format)

2. **Previous Output:**
   - ✓ Contains `assignments` array
   - ✓ Contains `solverRun` and `score`

3. **Employee Changes:**
   - ✓ New joiner `availableFrom` is within solve window
   - ✓ Departure `notAvailableFrom` is valid date
   - ✓ Leave dates: `leaveFrom <= leaveTo`

4. **Schema Version:**
   - ✓ Must be `"0.80"`

---

## Common Patterns

### Re-solve Entire Month with New Employee

```json
{
  "temporalWindow": {
    "cutoffDate": "2025-11-30",  // Before month start
    "solveFromDate": "2025-12-01",
    "solveToDate": "2025-12-31"
  },
  "employeeChanges": {
    "newJoiners": [{ /* new employee */ }]
  }
}
```

### Lock First Half, Re-solve Second Half

```json
{
  "temporalWindow": {
    "cutoffDate": "2025-12-15",
    "solveFromDate": "2025-12-16",
    "solveToDate": "2025-12-31"
  }
}
```

### Only Reassign Unassigned Slots

Load `previousOutput` with existing assignments, set temporal window to cover dates with UNASSIGNED slots, and add new employees if needed.

---

## Files & Endpoints

### Input Schema
`context/schemas/incremental_input_schema_v0.80.json`

### API Endpoint
`POST /solve/incremental`

### Pydantic Models
`src/models.py` - `IncrementalSolveRequest`

### Core Logic
`src/incremental_solver.py` - `solve_incremental()`

### Solver Integration
`context/engine/solver_engine.py` - Incremental mode support

### Test Suite
`test_incremental_phase2.py`

---

## Implementation Status

✅ **COMPLETED** (v0.80)

- [x] Pydantic models for validation
- [x] Temporal window validation
- [x] Slot classification (LOCKED vs SOLVABLE)
- [x] Employee pool merging (new joiners, departures, leave)
- [x] Locked hours/consecutive days calculation
- [x] Solver engine integration
- [x] Constraint context passing
- [x] Output merging with audit trail
- [x] API endpoint `/solve/incremental`
- [x] Test suite with 3 scenarios
- [x] JSON schema validation

---

## Quick Start

1. **Run initial solve** to get baseline roster:
   ```bash
   curl -X POST "https://ngrssolver08.comcentricapps.com/solve" \
     -d @input/december_2025.json -o output/baseline.json
   ```

2. **Create incremental request** with:
   - `previousOutput`: Load `output/baseline.json`
   - `temporalWindow`: Define lock/solve dates
   - `employeeChanges`: Add new joiners / mark departures

3. **Submit incremental solve**:
   ```bash
   curl -X POST "https://ngrssolver08.comcentricapps.com/solve/incremental" \
     -d @input/incremental_request.json -o output/updated_roster.json
   ```

4. **Analyze result**:
   - Check `incrementalSolve` block for statistics
   - Verify `auditInfo.source` to distinguish locked vs new assignments

---

## Related Documentation

- [INCREMENTAL_SOLVER_GUIDE.md](INCREMENTAL_SOLVER_GUIDE.md) - Detailed implementation guide
- [API_QUICK_REFERENCE.md](API_QUICK_REFERENCE.md) - All API endpoints
- [DEPLOYMENT_v0.95.md](DEPLOYMENT_v0.95.md) - Deployment guide

---

## Summary

The **Re-Roster / Incremental Solve** feature allows you to:
- ✅ Lock confirmed assignments (before cutoffDate)
- ✅ Add new employees mid-month
- ✅ Handle departures and long leave
- ✅ Re-solve only affected slots
- ✅ Maintain full audit trail
- ✅ Respect all constraints with locked context

**Endpoint:** `POST /solve/incremental`  
**Schema:** v0.80  
**Status:** ✅ Fully Implemented and Tested
