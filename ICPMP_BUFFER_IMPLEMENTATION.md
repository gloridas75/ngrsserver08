# ICPMP Buffer Implementation

## Problem
ICPMP v3 calculates the mathematically optimal employee count, but this can lead to infeasibility due to:
- Tight scheduling constraints (consecutive days, weekly/monthly hours)
- Rotation offset distribution gaps
- Insufficient flexibility for CP-SAT to find valid assignments

**Example**: With 39 available employees and headcount=10, ICPMP selected 17 employees → 72 unfilled slots

## Solution
Added configurable buffer percentage to increase ICPMP's employee selection beyond the mathematical optimum.

### Implementation
**File**: `src/preprocessing/icpmp_integration.py`  
**Method**: `_select_and_assign_employees()`

```python
# Apply buffer to increase employee count (default 20% buffer)
buffer_percentage = requirement.get('icpmpBufferPercentage', 20)  # Default 20%

if buffer_percentage > 0:
    optimal_count = int(optimal_count_raw * (1 + buffer_percentage / 100))
    logger.info(f"Applying {buffer_percentage}% buffer: {optimal_count_raw} → {optimal_count} employees")
```

### Usage in Input JSON
Add `icpmpBufferPercentage` field to each requirement:

```json
{
  "demandItems": [{
    "requirements": [{
      "requirementId": "185_1",
      "headcount": 10,
      "workPattern": ["D", "D", "D", "D", "D", "O", "O"],
      "icpmpBufferPercentage": 30,  // ← Add this field
      "enableOtAwareIcpmp": true
    }]
  }]
}
```

## Test Results (RST-20251228-D2C42C66)

| Buffer % | ICPMP Selects | Unfilled Slots | Status |
|----------|---------------|----------------|--------|
| 0%       | 17 employees  | 72 slots       | ❌ INFEASIBLE |
| 20%      | 20 employees  | 30 slots       | ❌ INFEASIBLE |
| 30%      | 22 employees  | 2 slots        | ⚠️ Near-optimal |
| 35%      | 22 employees  | 2 slots        | ⚠️ Near-optimal |

### Analysis
- **Original ICPMP count**: 17 employees (43.6% utilization)
- **Pattern**: DDDDDOO (7-day cycle, 5 work days)
- **Headcount needed**: 10 per day
- **Theoretical minimum**: ~14 employees (10 × 7 ÷ 5 = 14)
- **Practical minimum**: ~23-24 employees due to constraints

### Recommendations
- **Default buffer**: 20-30% for most scenarios
- **Tight patterns** (high consecutive days): 30-40%
- **Flexible patterns**: 10-20%
- **Set to 0** to use pure ICPMP optimal count

## Benefits
1. **Reduced infeasibility**: Provides CP-SAT more employees to work with
2. **Better coverage**: Extra employees fill scheduling gaps
3. **Flexibility**: Configurable per requirement
4. **Backward compatible**: Defaults to 20% if not specified

## Offset Distribution
When buffer increases employee count, offsets are extended cyclically:

```python
# Original: {0: 3, 1: 3, 2: 3, 3: 2, 4: 2, 5: 2, 6: 2} = 17 employees
# With 30% buffer → 22 employees needed
# Extended: [0,0,0,1,1,1,2,2,2,3,3,4,4,5,5,6,6,0,1,2,3,4] = 22 employees
```

The extension maintains offset balance while adding extra employees cyclically.

## Deployment Notes
- ✅ Code implemented in `icpmp_integration.py`
- ✅ Tested locally with various buffer percentages
- ⚠️ Needs deployment to production server
- 📝 Update API documentation with new field

## Future Enhancements
- Auto-calculate optimal buffer based on constraint tightness
- Per-scheme default buffers (Scheme A + APO may need higher buffer)
- Dynamic buffer adjustment during solve (if infeasible, retry with higher buffer)
