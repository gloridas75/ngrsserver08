# API Validation Fix - outcomeBased Mode

## Issue Summary

**Problem**: When testing `outcomeBased` mode via the `/solve/async` API endpoint, validation error occurred:
```
Invalid combination: rosteringBasis='demandBased' cannot use fixedRotationOffset='ouOffsets'. 
Valid modes for demandBased: ['auto', 'solverOptimized']
```

**Root Cause**: The `offset_manager.py` validation code was only checking `input_data.get('rosteringBasis')` at the root level, not checking `demandItems[0].rosteringBasis` where the value was actually specified.

## Solution

### Code Changes (Commit 5e1507e)

**File**: `src/offset_manager.py`

1. **Added import**:
```python
from context.engine.data_loader import extract_rostering_basis
```

2. **Updated extraction in `ensure_staggered_offsets()`** (line 349):
```python
# OLD (only checked root):
rostering_basis_raw = input_data.get('rosteringBasis')

# NEW (backward compatible):
rostering_basis_raw = extract_rostering_basis(input_data)
```

### How `extract_rostering_basis()` Works

From `context/engine/data_loader.py` (lines 41-61):
```python
def extract_rostering_basis(data: Dict[str, Any]) -> str:
    """
    Extract rosteringBasis with backward compatibility.
    
    Priority:
    1. demandItems[0].rosteringBasis (v0.95+)
    2. root.rosteringBasis (legacy)
    3. Default: 'demandBased'
    """
    demand_items = data.get('demandItems', [])
    if demand_items and len(demand_items) > 0:
        basis = demand_items[0].get('rosteringBasis')
        if basis:
            return basis
    
    return data.get('rosteringBasis', 'demandBased')
```

## Validation Logic

### Valid Combinations

From `offset_manager.py` (lines 82-117):
```python
valid_combinations = {
    "demandBased": ["auto", "solverOptimized"],
    "outcomeBased": ["ouOffsets"]
}
```

- ✅ `demandBased` + `auto` or `solverOptimized`
- ✅ `outcomeBased` + `ouOffsets`
- ❌ `demandBased` + `ouOffsets` → ValueError
- ❌ `outcomeBased` + `auto` or `solverOptimized` → ValueError

## Testing

### Test Input Structure

```json
{
  "rosteringBasis": null,  // ← Root level (empty)
  "demandItems": [
    {
      "rosteringBasis": "outcomeBased",  // ← Actual value here
      "minStaffThresholdPercentage": 100
    }
  ],
  "fixedRotationOffset": "ouOffsets",
  "ouOffsets": [
    {"ouId": "SAO", "rotationOffset": 1}
  ]
}
```

### Before Fix
```
❌ Error: Invalid combination: rosteringBasis='demandBased' cannot use fixedRotationOffset='ouOffsets'
   Reason: Only read root.rosteringBasis (null → defaulted to 'demandBased')
```

### After Fix
```
✅ Validation PASSED!
   Detected rosteringBasis: outcomeBased (from demandItems[0])
   Accepts: outcomeBased + ouOffsets
```

## Impact

### Files Modified
- `src/offset_manager.py` (2 lines changed)

### API Endpoints Affected
- POST `/solve` (synchronous)
- POST `/solve/async` (asynchronous)

Both endpoints call `ensure_staggered_offsets()` which includes the validation.

### Backward Compatibility
✅ **Fully backward compatible**

- Old inputs with `root.rosteringBasis` still work
- New inputs with `demandItems[0].rosteringBasis` now work
- Defaults to `demandBased` if not specified

## Verification

### CLI Test (Already Working)
```bash
python src/run_solver.py --in RST-20251218-BF734779_Solver_Input.json --time 60
# ✅ OPTIMAL solution, 56/56 employees used, 1736 slots created
```

### API Test (Now Fixed)
```bash
curl -X POST http://localhost:8080/solve/async \
  -H "Content-Type: application/json" \
  -d @RST-20251218-BF734779_Solver_Input.json

# ✅ Should now accept the input and create job
```

## Related Commits

1. **7a7c6ef** - Initial outcomeBased implementation
2. **78834d3** - Fix target calculation timing
3. **3117a82** - Override headcount for outcomeBased mode
4. **5e1507e** - Fix API validation (this commit)

## References

- [CONSTRAINT_ARCHITECTURE.md](../implementation_docs/CONSTRAINT_ARCHITECTURE.md) - Input processing flow
- [context/engine/data_loader.py](../context/engine/data_loader.py) - `extract_rostering_basis()` function
- [src/offset_manager.py](../src/offset_manager.py) - Validation logic
- Production input: `RST-20251218-BF734779_Solver_Input.json`
