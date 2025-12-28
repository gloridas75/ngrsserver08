# Incremental Solver Updates Required

**Date**: 2025-12-27  
**Context**: Recent solver changes require incremental solver updates

---

## Summary of Required Changes

The incremental solver needs **4 critical updates** to align with recent main solver improvements:

1. ✅ **Add input validation** (high priority)
2. ✅ **Support rosteringBasis modes** (high priority)
3. ✅ **Update schema version** (medium priority)
4. ✅ **Preserve ICPMP context** (optimization)

---

## Change 1: Add Input Validation (HIGH PRIORITY)

### Issue
Incremental solver doesn't validate input before passing to main solver.

### Impact
- `headcount: 0` validation won't trigger
- Invalid temporal windows pass through
- Schema mismatches not caught early

### Solution

**File**: `src/incremental_solver.py`  
**Function**: `solve_incremental()` (line 340)

**Add validation step:**

```python
def solve_incremental(
    request_data: Dict[str, Any],
    solver_engine: Any,
    run_id: str
) -> Dict[str, Any]:
    logger.info("=" * 80)
    logger.info("[INCREMENTAL SOLVER STARTING]")
    logger.info("=" * 80)
    
    # NEW: Validate incremental request structure
    _validate_incremental_request(request_data)
    
    # Extract components
    temporal_window = request_data["temporalWindow"]
    previous_output = request_data["previousOutput"]
    employee_changes = request_data["employeeChanges"]
    demand_items = request_data["demandItems"]
    planning_horizon = request_data["planningHorizon"]
    
    # Step 1: Validate temporal window
    validate_temporal_window(temporal_window)
    
    # NEW: Validate the solver input that will be passed to main solver
    from src.input_validator import validate_input
    
    # Build a test input to validate demand structure
    test_input = {
        "schemaVersion": request_data.get("schemaVersion", "0.95"),
        "demandItems": demand_items,
        "employees": [],  # Minimal for validation
        "planningHorizon": planning_horizon
    }
    
    validation_result = validate_input(test_input)
    if not validation_result.is_valid:
        error_msgs = [f"{e.field}: {e.message}" for e in validation_result.errors]
        raise IncrementalSolverError(f"Input validation failed: {'; '.join(error_msgs)}")
    
    logger.info(f"✓ Incremental input validated successfully")
    
    # ... rest of existing code
```

**Add helper function:**

```python
def _validate_incremental_request(request_data: Dict[str, Any]) -> None:
    """Validate incremental solve request structure."""
    
    required = ["temporalWindow", "previousOutput", "employeeChanges", 
                "demandItems", "planningHorizon", "planningReference"]
    
    missing = [f for f in required if f not in request_data]
    if missing:
        raise IncrementalSolverError(f"Missing required fields: {', '.join(missing)}")
    
    # Validate previousOutput has assignments
    if "assignments" not in request_data["previousOutput"]:
        raise IncrementalSolverError("previousOutput must contain 'assignments' array")
    
    logger.info("✓ Incremental request structure validated")
```

---

## Change 2: Support rosteringBasis Modes (HIGH PRIORITY)

### Issue
Incremental solver assumes demandBased mode (pattern-based). Doesn't handle outcomeBased (template-based).

### Impact
- Locked hour/day calculations may be incorrect for outcomeBased
- Template-based rosters can't use incremental solving
- Slot-based outcome mode not supported

### Solution

**File**: `src/incremental_solver.py`  
**Function**: `solve_incremental()` (line 340)

**Add rosteringBasis detection:**

```python
def solve_incremental(
    request_data: Dict[str, Any],
    solver_engine: Any,
    run_id: str
) -> Dict[str, Any]:
    # ... existing validation code ...
    
    # NEW: Detect rostering basis
    rostering_basis = _detect_rostering_basis(demand_items)
    logger.info(f"Detected rostering basis: {rostering_basis}")
    
    # ... existing classification code ...
    
    # Step 4: Calculate locked context for constraints (MODE-DEPENDENT)
    if rostering_basis == 'demandBased':
        # Pattern-based: Calculate locked hours/days
        locked_weekly_hours = calculate_locked_weekly_hours(locked_assignments, temporal_window)
        locked_consecutive_days = calculate_locked_consecutive_days(locked_assignments, temporal_window)
        logger.info(f"✓ Calculated locked context for demandBased mode")
    else:
        # outcomeBased: No pattern continuity needed
        locked_weekly_hours = {}
        locked_consecutive_days = {}
        logger.info(f"✓ Skipped pattern continuity for outcomeBased mode (template-based)")
    
    # ... rest of existing code ...
```

**Add helper function:**

```python
def _detect_rostering_basis(demand_items: List[Dict[str, Any]]) -> str:
    """
    Detect rostering basis from demand items.
    
    Priority:
    1. demandItems[0].rosteringBasis
    2. Default: 'demandBased'
    """
    if demand_items and len(demand_items) > 0:
        rostering_basis = demand_items[0].get('rosteringBasis')
        if rostering_basis:
            return rostering_basis
    
    return 'demandBased'
```

**Update slot classification for outcomeBased:**

For outcomeBased mode, the "locked" concept may be different:
- Template-based rosters have no rotation continuity
- Locked assignments are just historical (before cutoff)
- No need to track consecutive days or weekly patterns

**Optional**: Add warning for outcomeBased:

```python
if rostering_basis == 'outcomeBased':
    logger.warning("⚠️  Incremental solving for outcomeBased mode is experimental")
    logger.warning("    Template-based rosters may not maintain assignment patterns")
```

---

## Change 3: Update Schema Version (MEDIUM PRIORITY)

### Issue
`IncrementalSolveRequest` hardcodes schema version `0.80` (outdated).

### Impact
- Clients using newer schemas (0.95, 0.98) may have issues
- Schema validation may fail

### Solution

**File**: `src/models.py`  
**Line**: 391

**Before:**
```python
schemaVersion: str = Field(
    "0.80", 
    description="Schema version for incremental solve"
)
```

**After:**
```python
schemaVersion: str = Field(
    "0.95",  # Updated to match current solver version
    description="Schema version for incremental solve (0.95, 0.98)"
)
```

**Also update documentation:**

```python
class IncrementalSolveRequest(BaseModel):
    """
    Request payload for POST /solve/incremental endpoint.
    
    Supports schema versions: 0.95, 0.98
    (Legacy 0.80 compatibility maintained)
    """
```

---

## Change 4: Preserve ICPMP Context (OPTIMIZATION)

### Issue
Incremental solver doesn't preserve ICPMP preprocessing results from original solve.

### Impact
- Main solver may run ICPMP again (wasteful)
- Optimized offsets from original solve are lost
- Inconsistent employee selection between original and incremental

### Solution

**File**: `src/incremental_solver.py`  
**Function**: `build_employee_pool()` (line 176)

**Before:**
```python
def build_employee_pool(
    previous_output: Dict[str, Any],
    new_joiners: List[Dict[str, Any]],
    departed_employee_ids: Set[str],
    temporal_window: Dict[str, str]
) -> List[Dict[str, Any]]:
    # ... existing code to extract employees ...
```

**After:**
```python
def build_employee_pool(
    previous_output: Dict[str, Any],
    new_joiners: List[Dict[str, Any]],
    departed_employee_ids: Set[str],
    temporal_window: Dict[str, str]
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Build employee pool for incremental solve.
    
    Returns:
        Tuple of (employee_list, icpmp_context_or_None)
    """
    # ... existing employee extraction code ...
    
    # NEW: Extract ICPMP preprocessing context if available
    icpmp_context = None
    if "icpmpPreprocessing" in previous_output:
        icpmp_context = previous_output["icpmpPreprocessing"]
        logger.info(f"✓ Preserved ICPMP context from previous solve")
        logger.info(f"   - Filtered employees: {len(icpmp_context.get('filtered_employees', []))}")
        logger.info(f"   - Optimized offsets: {len(icpmp_context.get('optimized_offsets', {}))}")
    
    return all_employees, icpmp_context
```

**Update `solve_incremental()` to use ICPMP context:**

```python
# Step 3: Build employee pool
all_employees, icpmp_context = build_employee_pool(
    previous_output=previous_output,
    new_joiners=employee_changes.get("newJoiners", []),
    departed_employee_ids=departed_employee_ids,
    temporal_window=temporal_window
)

# Step 5: Build modified input for solver
incremental_input = {
    "schemaVersion": request_data.get("schemaVersion", "0.95"),
    "planningReference": request_data["planningReference"],
    "planningHorizon": planning_horizon,
    "demandItems": demand_items,
    "employees": all_employees,
    "solverConfig": request_data.get("solverConfig", {}),
    
    # Pass incremental context
    "_incremental": {
        "mode": "incremental",
        "lockedAssignments": locked_assignments,
        "solvableSlots": solvable_slots,
        "lockedWeeklyHours": locked_weekly_hours,
        "lockedConsecutiveDays": locked_consecutive_days,
        "temporalWindow": temporal_window,
        "employeeChanges": employee_changes,
        "icpmpContext": icpmp_context  # NEW: Pass ICPMP context
    }
}
```

**Update main solver to use preserved ICPMP:**

**File**: `src/solver.py` (would need update)

Check if `ctx.get('_incremental', {}).get('icpmpContext')` exists:
- If yes: Skip ICPMP preprocessing, use cached results
- If no: Run ICPMP normally

---

## Testing Requirements

### Test Cases Needed

1. **Incremental with outcomeBased mode:**
   ```json
   {
     "demandItems": [{
       "rosteringBasis": "outcomeBased",
       "minStaffThresholdPercentage": 100
     }],
     "employeeChanges": {
       "newJoiners": [...]
     }
   }
   ```

2. **Incremental with headcount=0:**
   ```json
   {
     "demandItems": [{
       "rosteringBasis": "outcomeBased",
       "requirements": [{
         "headcount": 0
       }]
     }]
   }
   ```

3. **Incremental with ICPMP context preservation:**
   - Check that ICPMP doesn't re-run for incremental solve
   - Verify offsets are preserved from original

4. **Incremental with invalid input:**
   - Should fail early with clear error message
   - Test missing fields, invalid temporal window

### Test Scripts

Create: `test_scripts/test_incremental_updates.py`

```python
#!/usr/bin/env python3
"""Test incremental solver with recent changes."""

import json
import requests

def test_incremental_with_outcomebased():
    """Test incremental solve with outcomeBased mode."""
    payload = {
        "schemaVersion": "0.95",
        "planningReference": "INCR-TEST-001",
        "temporalWindow": {
            "cutoffDate": "2026-01-10",
            "solveFromDate": "2026-01-11",
            "solveToDate": "2026-01-31"
        },
        "previousOutput": {...},  # Previous outcomeBased solve
        "employeeChanges": {
            "newJoiners": [{...}]
        },
        "demandItems": [{
            "rosteringBasis": "outcomeBased",
            "requirements": [{"headcount": 0}]  # Test headcount=0
        }],
        "planningHorizon": {...}
    }
    
    response = requests.post(
        "http://localhost:8080/solve/incremental",
        json=payload
    )
    
    assert response.status_code == 200
    result = response.json()
    assert "incrementalSolve" in result
    print("✓ Incremental with outcomeBased mode works")

if __name__ == "__main__":
    test_incremental_with_outcomebased()
```

---

## Priority and Timeline

| Change | Priority | Estimated Effort | Risk |
|--------|----------|------------------|------|
| 1. Input validation | **HIGH** | 2 hours | Low |
| 2. rosteringBasis support | **HIGH** | 4 hours | Medium |
| 3. Schema version update | **MEDIUM** | 30 min | Low |
| 4. ICPMP context preservation | **LOW** | 3 hours | Medium |

**Total Estimated Effort**: 1-2 days

---

## Backward Compatibility

All changes are **backward compatible**:

✅ Existing incremental requests (demandBased) continue working  
✅ New validation only catches errors (doesn't break valid inputs)  
✅ outcomeBased support is additive (doesn't affect demandBased)  
✅ ICPMP context is optional (falls back to re-running if not present)

---

## Recommendation

**Implement Changes 1 and 2 immediately** (input validation + rosteringBasis support).

These are critical for:
- Supporting your recent `headcount: 0` fix
- Enabling incremental solving for outcomeBased rosters
- Catching invalid inputs early (better error messages)

Changes 3 and 4 can be deferred but should be done before next release.

---

## Next Steps

1. ✅ Implement input validation in `solve_incremental()`
2. ✅ Add rosteringBasis detection and conditional logic
3. ✅ Update schema version in `IncrementalSolveRequest`
4. ✅ Test with outcomeBased inputs
5. ⏳ (Optional) Preserve ICPMP context for optimization
6. ⏳ Update API documentation

