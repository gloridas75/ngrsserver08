# Shift Definitions Feature

## Overview

The ICPMP Configuration Optimizer now supports custom shift hour definitions through the optional `shiftDefinitions` parameter. This enables accurate staffing calculations for different shift types (e.g., 8-hour Scheme P shifts vs. 12-hour standard shifts).

## Motivation

Previously, the optimizer hardcoded shift hours at **11.0 net hours** (12 gross - 1 lunch). This caused inaccurate calculations for:
- **Scheme P** (8-hour shifts): Actual net hours = 7.0
- **Non-standard shifts**: Varying gross hours or lunch breaks
- **Mixed shift environments**: Different shift types with different durations

The weekly hour constraint (`maxWeeklyNormalHours: 44`) directly impacts how many days an employee can work:
- 12-hour shifts (11h net): 44 ÷ 11 = **4 days/week**
- 8-hour shifts (7h net): 44 ÷ 7 = **6.3 days/week** (~5-6 days)

Using incorrect hours leads to under/over-staffing.

## Implementation

### 1. Schema Definition

Add an optional `shiftDefinitions` object to your configuration request:

```json
{
  "shiftDefinitions": {
    "<SHIFT_CODE>": {
      "grossHours": <number>,
      "lunchBreak": <number>,
      "description": "<string>"  // Optional
    }
  },
  "requirements": [...],
  "constraints": {...},
  "planningHorizon": {...}
}
```

### 2. Example: Scheme P (8-Hour Shifts)

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
    },
    "N": {
      "grossHours": 8.0,
      "lunchBreak": 1.0,
      "description": "Night shift (8h gross, 7h net)"
    }
  },
  "requirements": [
    {
      "id": "REQ_SCHEME_P",
      "shiftTypes": ["W", "E", "N"],
      "headcountPerShift": {"W": 2, "E": 1, "N": 1},
      "scheme": "P"
    }
  ]
}
```

### 3. Example: Standard 12-Hour Shifts

```json
{
  "shiftDefinitions": {
    "D": {
      "grossHours": 12.0,
      "lunchBreak": 1.0,
      "description": "Day shift (12h gross, 11h net)"
    },
    "N": {
      "grossHours": 12.0,
      "lunchBreak": 1.0,
      "description": "Night shift (12h gross, 11h net)"
    }
  },
  "requirements": [
    {
      "id": "REQ_STANDARD",
      "shiftTypes": ["D", "N"],
      "headcountPerShift": {"D": 4, "N": 4}
    }
  ]
}
```

### 4. Default Behavior

If `shiftDefinitions` is **not provided**, all shifts default to:
- **11.0 net hours** (12 gross - 1 lunch)

This maintains backward compatibility with existing configurations.

## Impact on Staffing Calculations

### Scenario: 4 employees needed per day, 44h/week max

| Shift Type | Net Hours | Days/Week | Employees Needed | Pattern |
|------------|-----------|-----------|------------------|---------|
| **12-hour** (default) | 11.0 | 4 | 7 | `DDDDO` |
| **8-hour** (Scheme P) | 7.0 | 5-6 | 5 | `DDDDDO` |

**Why the difference?**
- 12-hour shifts: Employee works 4 days (44h), needs 7 people for 4-per-day
- 8-hour shifts: Employee can work 5-6 days (35-42h), needs only 5 people

## API Changes

### Request Schema

Added optional field to `/configure` endpoint:

```json
{
  "shiftDefinitions": {  // NEW: Optional
    "D": {"grossHours": 12.0, "lunchBreak": 1.0},
    "N": {"grossHours": 12.0, "lunchBreak": 1.0}
  },
  "requirements": [...],
  "constraints": {...},
  "planningHorizon": {...}
}
```

### Response Schema

No changes to response structure. The optimizer uses shift definitions internally for calculations.

## Code Changes

### `context/engine/config_optimizer.py`

**Functions Updated:**
- `optimize_requirement_config()` - Added `shift_definitions: Optional[Dict[str, Dict]] = None`
- `optimize_all_requirements()` - Added `shift_definitions: Optional[Dict[str, Dict]] = None`

**Logic:**
```python
# Get shift-specific hours
if shift_definitions and shift in shift_definitions:
    shift_def = shift_definitions[shift]
    gross_hours = shift_def.get('grossHours', 12.0)
    lunch_break = shift_def.get('lunchBreak', 1.0)
    shift_hours = gross_hours - lunch_break
else:
    shift_hours = 11.0  # Default
```

### `src/api_server.py`

**Changes:**
```python
# Extract optional shift definitions
shift_definitions = config_input.get("shiftDefinitions", None)

# Pass to optimizer
optimized_result = optimize_all_requirements(
    requirements=config_input["requirements"],
    constraints=constraints,
    planning_horizon=config_input["planningHorizon"],
    shift_definitions=shift_definitions  # NEW
)
```

## Test Files

### `input/requirements_with_shift_definitions.json`
Complete example with 8-hour Scheme P shifts (W, E, N).

### `input/comparison_12h_vs_8h.json`
Side-by-side comparison showing impact of different shift hours.

## Testing

```bash
# Test with 8-hour shifts
curl -X POST http://localhost:8000/configure \
  -H "Content-Type: application/json" \
  -d @input/requirements_with_shift_definitions.json

# Test comparison
curl -X POST http://localhost:8000/configure \
  -H "Content-Type: application/json" \
  -d @input/comparison_12h_vs_8h.json
```

## Backward Compatibility

✅ **Fully backward compatible**
- Existing configurations work without changes
- Default behavior (11.0h) preserved when `shiftDefinitions` is omitted
- No breaking changes to API or response format

## Use Cases

1. **Scheme P Optimization**: Accurate staffing for 8-hour shift schemes
2. **Mixed Shift Types**: Different hours for D/N/E shifts in same requirement
3. **Non-Standard Hours**: Custom gross hours or lunch break durations
4. **What-If Analysis**: Compare staffing needs across different shift configurations

## Future Enhancements

Potential improvements:
- Validate shift codes in `requirements.shiftTypes` match `shiftDefinitions` keys
- Support overtime multipliers per shift type
- Add shift-specific constraints (e.g., `maxConsecutiveNights`)
- Include shift definitions in output for transparency

## Git Commit

**Commit:** `b1cf487`  
**Date:** Nov 25, 2025  
**Branch:** `main`

Files changed:
- `context/engine/config_optimizer.py`
- `src/api_server.py`
- `postman/README.md`
- `input/requirements_with_shift_definitions.json` (new)
- `input/comparison_12h_vs_8h.json` (new)
