# Input JSON Field Reference: fallbackToOutcomeBased

## Quick Reference

**Added in:** v0.98+  
**Type:** Boolean  
**Default:** `true` (enabled)  
**Location:** Root level of input JSON

## Usage

```json
{
  "schemaVersion": "0.98",
  "rosteringBasis": "demandBased",
  "fallbackToOutcomeBased": true,  // ← Controls automatic mode switching
  "employees": [...],
  "demandItems": [...]
}
```

## Values

| Value | Behavior |
|-------|----------|
| `true` | **Enabled** (default) - Automatically switch to outcomeBased if ICPMP fails |
| `false` | **Disabled** - Stay in demandBased mode even if ICPMP fails |
| (omitted) | **Enabled** - Defaults to `true` |

## When It Matters

This field only applies when:
1. `rosteringBasis` = "demandBased"
2. ICPMP preprocessing fails due to insufficient employees

If ICPMP succeeds, this field has no effect.

## Examples

### Example 1: Automatic Fallback (Recommended)

**Input:**
```json
{
  "schemaVersion": "0.98",
  "rosteringBasis": "demandBased",
  "fallbackToOutcomeBased": true,
  "employees": [
    {"employeeId": "EMP001", "scheme": "A", "product": "APO"}
  ],
  "demandItems": [{
    "requirements": [{
      "workPattern": ["D","D","D","D","D","O","O"]  // 7-day pattern
    }]
  }]
}
```

**Result:**
```
[CLI] ❌ ICPMP preprocessing failed: Need 7, but only 1 available
[CLI] ⚠️  AUTOMATIC FALLBACK ACTIVATED
[CLI] Switching from 'demandBased' → 'outcomeBased' rostering
[CLI] Status: OPTIMAL
[CLI] Assignments: 23 assigned, 0 unassigned
```

### Example 2: Fallback Disabled

**Input:**
```json
{
  "rosteringBasis": "demandBased",
  "fallbackToOutcomeBased": false,  // ← Explicit disable
  "employees": [{"employeeId": "EMP001"}]
}
```

**Result:**
```
[CLI] ❌ ICPMP preprocessing failed: Need 7, but only 1 available
[CLI] ⚠️  No employees selected! Automatic fallback disabled.
[CLI] ℹ️  Tip: Set 'fallbackToOutcomeBased': true to enable automatic mode switching
[CLI] Status: INFEASIBLE
```

### Example 3: Direct outcomeBased (No Fallback Needed)

**Input:**
```json
{
  "rosteringBasis": "outcomeBased",  // ← Already in outcomeBased mode
  "fallbackToOutcomeBased": true,    // ← No effect (already in target mode)
  "employees": [{"employeeId": "EMP001"}]
}
```

**Result:**
```
[CLI] ======================================================================
[CLI] OUTCOME-BASED ROSTERING MODE
[CLI] ======================================================================
[CLI] Status: OPTIMAL
```

## Decision Tree

```
┌─────────────────────────────────────┐
│   rosteringBasis = "demandBased"?   │
└─────────────┬───────────────────────┘
              │
              ├─ NO → Use specified mode (no fallback)
              │
              └─ YES → Run ICPMP preprocessing
                       │
                       ├─ ICPMP SUCCESS → Use demandBased (rotation-based)
                       │
                       └─ ICPMP FAILURE (insufficient employees)
                                │
                                ├─ fallbackToOutcomeBased = true?
                                │  │
                                │  ├─ YES → ✓ Switch to outcomeBased
                                │  │         (template-based rostering)
                                │  │
                                │  └─ NO → ❌ Continue with 0 employees
                                │           (INFEASIBLE result)
```

## Best Practices

### ✅ Recommended

Always include `fallbackToOutcomeBased: true` explicitly:

```json
{
  "rosteringBasis": "demandBased",
  "fallbackToOutcomeBased": true,  // ← Explicit for documentation
  ...
}
```

**Why:**
- Makes the feature visible in your input JSON
- Reminds users that automatic fallback exists
- Self-documenting input files

### ❌ Avoid

Don't disable fallback unless you specifically need ICPMP-only behavior:

```json
{
  "rosteringBasis": "demandBased",
  "fallbackToOutcomeBased": false,  // ← Only if you need strict demandBased
  ...
}
```

**When to disable:**
- Testing ICPMP behavior specifically
- Validating rotation coverage requirements
- Debugging employee assignment logic

## Migration Notes

### Backward Compatibility

**Existing inputs without this field:**
- Automatically default to `true` (fallback enabled)
- No changes needed to existing inputs
- Behavior improves automatically (previously INFEASIBLE scenarios may now succeed)

### From v0.95 to v0.98

**Before (v0.95):**
```json
{
  "rosteringBasis": "demandBased",
  "employees": [{"employeeId": "EMP001"}]
}
```
Result: ❌ INFEASIBLE (Need 7, have 1)

**After (v0.98):**
```json
{
  "rosteringBasis": "demandBased",
  // fallbackToOutcomeBased defaults to true
  "employees": [{"employeeId": "EMP001"}]
}
```
Result: ✓ OPTIMAL (automatic fallback to outcomeBased)

## Output Indicators

Check `solverRun.icpmp` in output JSON:

```json
{
  "solverRun": {
    "icpmp": {
      "enabled": false,
      "fallback_triggered": true,
      "original_mode": "demandBased",
      "fallback_mode": "outcomeBased",
      "fallback_reason": "Failed to process requirement...",
      "warnings": ["Automatic fallback: ..."]
    }
  }
}
```

## Related Settings

| Setting | Purpose | Interaction |
|---------|---------|-------------|
| `rosteringBasis` | Primary rostering mode | Must be "demandBased" for fallback to apply |
| `fixedRotationOffset` | Offset assignment strategy | Used in both modes (different behavior) |
| `ouOffsets` | OU-based rotation offsets | Used in outcomeBased after fallback |

## See Also

- [Automatic Fallback Guide](AUTOMATIC_FALLBACK_GUIDE.md) - Complete feature documentation
- [ICPMP Guide](ICPMP_GUIDE.md) - demandBased rostering details
- [Template Roster Guide](TEMPLATE_ROSTER_GUIDE.md) - outcomeBased rostering details
- [Input Schema](../context/schemas/input_schema_v0.98.json) - Full input specification
