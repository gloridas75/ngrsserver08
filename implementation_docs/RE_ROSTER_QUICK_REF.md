# Re-Roster Quick Reference

## API Endpoint
```
POST /solve/incremental
```

## Minimal Example

```json
{
  "schemaVersion": "0.80",
  "planningReference": "DEC2025_v2",
  
  "temporalWindow": {
    "cutoffDate": "2025-12-15",      // Lock before this
    "solveFromDate": "2025-12-16",   // Solve from here
    "solveToDate": "2025-12-31"      // Until here
  },
  
  "previousOutput": {
    /* Paste your previous solver output here */
  },
  
  "employeeChanges": {
    "newJoiners": [
      {
        "employee": { /* Full employee object */ },
        "availableFrom": "2025-12-16"
      }
    ],
    "notAvailableFrom": [
      {
        "employeeId": "EMP001",
        "notAvailableFrom": "2025-12-20"
      }
    ],
    "longLeave": [
      {
        "employeeId": "EMP002",
        "leaveFrom": "2025-12-18",
        "leaveTo": "2025-12-22"
      }
    ]
  },
  
  "demandItems": [ /* Same as original solve */ ],
  "planningHorizon": { /* Same as original solve */ }
}
```

## Timeline Example

```
December 2025 Roster
│
├─── Dec 1-15 ────────┤───── Dec 16-31 ─────┤
│                     │                      │
│   LOCKED            │    SOLVABLE          │
│   (preserved)       │    (re-solve)        │
│                     │                      │
│                cutoffDate            solveToDate
│                (Dec 15)             (Dec 31)
│                     └─ solveFromDate (Dec 16)
```

## Use Cases

### 1. New Employee Joins
- Add to `newJoiners` array
- Set `availableFrom` date
- Unassigned slots filled with new employee

### 2. Employee Departs
- Add to `notAvailableFrom` array
- Set departure date
- Their future assignments freed and reassigned

### 3. Employee on Leave
- Add to `longLeave` array
- Set `leaveFrom` and `leaveTo`
- Assignments during leave freed and reassigned

### 4. Fix Unassigned Slots
- Load previous output
- Add more employees via `newJoiners`
- Re-solve to fill gaps

## Output Structure

```json
{
  "assignments": [
    {
      "date": "2025-12-10",
      "employeeId": "EMP001",
      "auditInfo": {
        "source": "locked",        // From previous solve
        "solverRunId": "SRN-001"
      }
    },
    {
      "date": "2025-12-20",
      "employeeId": "NEW001",
      "auditInfo": {
        "source": "incremental",   // From this solve
        "solverRunId": "SRN-002"
      }
    }
  ],
  
  "incrementalSolve": {
    "cutoffDate": "2025-12-15",
    "lockedCount": 385,
    "solvableCount": 297,
    "freedDepartedCount": 15,
    "freedLeaveCount": 8,
    "newJoinerCount": 1
  }
}
```

## Testing

```bash
# Submit incremental solve
curl -X POST "https://ngrssolver08.comcentricapps.com/solve/incremental" \
  -H "Content-Type: application/json" \
  -d @input/incremental_request.json

# Test file location
test_incremental_phase2.py

# Sample inputs
input/incremental/test_new_joiner.json
input/incremental/test_departure.json
input/incremental/test_long_leave.json
```

## Key Points

✅ **Locks assignments before cutoffDate**  
✅ **Re-solves from solveFromDate onwards**  
✅ **Merges new + existing employees**  
✅ **Respects all constraints**  
✅ **Full audit trail**

## Documentation

📖 Full Guide: `implementation_docs/RE_ROSTER_INPUT_FORMAT.md`  
📖 Implementation: `implementation_docs/INCREMENTAL_SOLVER_GUIDE.md`  
🔌 API Docs: `implementation_docs/API_QUICK_REFERENCE.md`
