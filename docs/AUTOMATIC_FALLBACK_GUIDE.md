# Automatic Fallback: demandBased → outcomeBased

## Overview

**Version:** 0.98+  
**Feature:** Automatic mode switching when ICPMP preprocessing fails

When `rosteringBasis` is set to "demandBased" but ICPMP preprocessing fails due to insufficient employees for rotation-based staffing, the solver can automatically fallback to "outcomeBased" (template-based) rostering.

## Problem Scenario

**Example:**
- Input: 1 employee
- Work Pattern: `['D','D','D','D','D','O','O']` (7-day rotation)
- Rostering Mode: `demandBased` (ICPMP)

**ICPMP Requirement:** 7-day pattern requires 7 employees (one per rotation offset)

**Result without fallback:** ❌ INFEASIBLE - "Need 7, but only 1 available"

## Solution: Automatic Fallback

The solver now automatically switches to `outcomeBased` mode when ICPMP fails, allowing constraint-driven scheduling that works with any number of employees.

## Configuration

### Input JSON Field

```json
{
  "schemaVersion": "0.98",
  "rosteringBasis": "demandBased",
  "fallbackToOutcomeBased": true,  // ← NEW FIELD (default: true)
  "employees": [...]
}
```

### Fallback Control

| Value | Behavior |
|-------|----------|
| `true` (default) | Enable automatic fallback |
| `false` | Disable fallback, remain in demandBased mode |

## Fallback Behavior

### When Fallback Triggers

1. **Mode:** `rosteringBasis` = "demandBased"
2. **ICPMP Failure:** Preprocessing fails with "Insufficient employees" error
3. **Setting:** `fallbackToOutcomeBased` = true (or omitted, defaults to true)

### What Happens

```
[CLI] ======================================================================
[CLI] ICPMP v3.0 PREPROCESSING (demandBased mode)
[CLI] ======================================================================
[CLI] Input: 1 employees, 0 have patterns
[CLI] ❌ ICPMP preprocessing failed: Insufficient employees for requirement...
[CLI] ⚠️  AUTOMATIC FALLBACK ACTIVATED
[CLI] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[CLI] Switching from 'demandBased' → 'outcomeBased' rostering
[CLI] Reason: Insufficient employees for rotation-based staffing
[CLI] Mode: Constraint-driven template validation (allows flexible scheduling)
[CLI] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[CLI] ======================================================================
[CLI] OUTCOME-BASED ROSTERING (TEMPLATE VALIDATION)
[CLI] ======================================================================
[CLI] Method: Generate template per OU → validate constraints → replicate
[CLI] Constraints: C1-C17 (core MOM regulatory constraints)

[CLI] ✓ Template roster generated in 0.00s
[CLI] Status: OPTIMAL
[CLI] Assignments: 23 assigned, 0 unassigned
```

### Output Metadata

The output JSON includes fallback information:

```json
{
  "solverRun": {
    "icpmp": {
      "enabled": false,
      "fallback_triggered": true,
      "original_mode": "demandBased",
      "fallback_mode": "outcomeBased",
      "fallback_reason": "Failed to process requirement 148_1: Insufficient employees...",
      "warnings": ["Automatic fallback: Failed to process requirement..."]
    }
  }
}
```

## Mode Comparison

### demandBased (ICPMP) - Rotation-Based

**Best for:** Multi-employee scenarios with rotation patterns

| Aspect | Behavior |
|--------|----------|
| **Employee count** | Must match pattern length (N-day pattern = N employees minimum) |
| **Rotation offsets** | Each offset = specific days in month |
| **Pattern interpretation** | FIXED rotation schedule |
| **Flexibility** | Rotation-locked, limited flexibility |
| **Example** | Pattern `['D','D','D','O']` with 4 employees:<br>- Emp 1 (offset 0): Days 1, 5, 9, 13, 17, 21, 25, 29<br>- Emp 2 (offset 1): Days 2, 6, 10, 14, 18, 22, 26, 30<br>- Emp 3 (offset 2): Days 3, 7, 11, 15, 19, 23, 27, 31<br>- Emp 4 (offset 3): Days 4, 8, 12, 16, 20, 24, 28 |

### outcomeBased (Template) - Constraint-Driven

**Best for:** Single/few employees, flexible scheduling

| Aspect | Behavior |
|--------|----------|
| **Employee count** | Works with any number (including 1) |
| **Rotation offsets** | Starting point in pattern only |
| **Pattern interpretation** | DESIRED template (constraints override) |
| **Flexibility** | High - constraints drive scheduling |
| **Example** | Pattern `['D','D','D','O']` with 1 employee:<br>- Work 3 days, off 1 day (as template)<br>- Constraints (C2, C3, C5, etc.) determine actual schedule<br>- Can adjust based on coverage days, hours limits, etc. |

## Use Cases

### Scenario 1: Single Employee Rostering

**Input:**
```json
{
  "rosteringBasis": "demandBased",
  "fallbackToOutcomeBased": true,
  "employees": [{"employeeId": "EMP001", ...}],
  "demandItems": [{
    "requirements": [{
      "workPattern": ["D","D","D","D","D","O","O"]
    }]
  }]
}
```

**Result:**
- ICPMP tries rotation-based (fails: need 7, have 1)
- Automatic fallback to outcomeBased
- Template-based scheduling succeeds
- ✓ OPTIMAL with constraint-driven assignments

### Scenario 2: Insufficient Employee Count

**Input:**
```json
{
  "rosteringBasis": "demandBased",
  "fallbackToOutcomeBased": true,
  "employees": [...],  // 3 employees
  "demandItems": [{
    "requirements": [{
      "workPattern": ["D","D","D","D","D","O","O"]  // Needs 7
    }]
  }]
}
```

**Result:**
- ICPMP fails (need 7, have 3)
- Automatic fallback to outcomeBased
- Template-based scheduling uses all 3 employees
- ✓ Flexible scheduling based on constraints

### Scenario 3: Fallback Disabled

**Input:**
```json
{
  "rosteringBasis": "demandBased",
  "fallbackToOutcomeBased": false,  // ← Explicit disable
  "employees": [{"employeeId": "EMP001", ...}]
}
```

**Result:**
- ICPMP fails
- ⚠️ Fallback disabled - continues with 0 employees
- ❌ INFEASIBLE (no employees to assign)

**Output:**
```
[CLI] ⚠️  No employees selected! Automatic fallback disabled.
[CLI] ℹ️  Tip: Set 'fallbackToOutcomeBased': true to enable automatic mode switching
```

## Migration Guide

### Existing Users

**No action required** - fallback is **enabled by default**.

Your existing `demandBased` inputs will automatically fallback if ICPMP fails.

### Explicit Control

To **disable** automatic fallback (retain old behavior):

```json
{
  "rosteringBasis": "demandBased",
  "fallbackToOutcomeBased": false  // ← Add this to disable
}
```

### Best Practice

**Recommended approach:**
```json
{
  "rosteringBasis": "demandBased",
  "fallbackToOutcomeBased": true,  // ← Explicit for documentation
  "demandItems": [...]
}
```

This makes the feature visible in the input JSON, so users remember it exists.

## API Endpoints

Both synchronous and asynchronous endpoints support the fallback feature:

### POST /solve (Synchronous)

```bash
curl -X POST http://localhost:8080/solve \
  -H "Content-Type: application/json" \
  -d '{
    "rosteringBasis": "demandBased",
    "fallbackToOutcomeBased": true,
    "employees": [...]
  }'
```

### POST /solve/async (Asynchronous)

```bash
curl -X POST http://localhost:8080/solve/async \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "rosteringBasis": "demandBased",
      "fallbackToOutcomeBased": true,
      "employees": [...]
    },
    "webhookUrl": "https://webhook.site/xyz"
  }'
```

## Error Detection

The fallback triggers when ICPMP returns:
- **Empty employee list** (0 employees selected)
- **Warning containing** "Insufficient employees"

Example warning:
```
"Failed to process requirement 148_1: Insufficient employees for requirement 148_1: 
Need 7, but only 1 available. Total eligible: 1, Already assigned: 0"
```

## Implementation Details

### Code Location

**File:** `src/solver.py`

**Logic:**
```python
# Check if fallback to outcomeBased is enabled (default: True)
fallback_enabled = input_data.get('fallbackToOutcomeBased', True)
original_rostering_basis = rostering_basis  # Store original for logging

# ... ICPMP preprocessing ...

# Check for ICPMP failures (empty employee list + warnings)
filtered_count = len(preprocessing_result['filtered_employees'])
has_insufficient_warning = any("Insufficient employees" in w 
                               for w in preprocessing_result.get('warnings', []))

if filtered_count == 0 and has_insufficient_warning and fallback_enabled:
    # AUTOMATIC FALLBACK: Switch to outcomeBased mode
    rostering_basis = 'outcomeBased'
    needs_icpmp = False
    input_data['employees'] = employees  # Restore original employee list
```

### Tests

Run existing tests to verify:
```bash
# All tests should pass with fallback enabled
pytest tests/ -q

# Test with real single-employee input
python src/run_solver.py --in input/single_employee.json --time 300
```

## FAQ

### Q: What is the default behavior?

**A:** Fallback is **enabled by default** (`fallbackToOutcomeBased: true`). If you omit the field, it defaults to `true`.

### Q: Will this change existing behavior?

**A:** Only for scenarios that **previously failed**. If your input worked before, it will continue to work the same way.

### Q: Should I always use demandBased with fallback enabled?

**A:** Yes, this is recommended. It provides automatic resilience:
- Multi-employee scenarios → ICPMP rotation-based (optimal)
- Insufficient employees → Fallback to template-based (flexible)

### Q: Can I force outcomeBased mode directly?

**A:** Yes! Set `"rosteringBasis": "outcomeBased"` directly. Fallback only applies when you start with "demandBased".

### Q: How do I know if fallback occurred?

**A:** Check the output JSON:
```json
{
  "solverRun": {
    "icpmp": {
      "fallback_triggered": true,
      "original_mode": "demandBased",
      "fallback_mode": "outcomeBased"
    }
  }
}
```

### Q: Does fallback affect solve time?

**A:** Minimal impact. ICPMP preprocessing fails quickly (< 0.1s), then template-based rostering runs normally.

### Q: Can I test both modes explicitly?

**A:** Yes!

**Test demandBased (with fallback):**
```bash
# Will automatically fallback if insufficient employees
python src/run_solver.py --in input.json --time 300
```

**Test outcomeBased (direct):**
```bash
# Change input: "rosteringBasis": "outcomeBased"
python src/run_solver.py --in input.json --time 300
```

## See Also

- [ICPMP Guide](ICPMP_GUIDE.md) - Understanding rotation-based rostering
- [Template Roster Guide](TEMPLATE_ROSTER_GUIDE.md) - Constraint-driven scheduling
- [Rotation Patterns](../context/domain/rotation_patterns.md) - Work pattern definitions
- [Constraint Architecture](../implementation_docs/CONSTRAINT_ARCHITECTURE.md) - How constraints work
