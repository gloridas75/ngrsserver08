# Fixed Rotation Offset Modes - User Guide

## Overview

The solver supports two **rostering philosophies** controlled by the `rosteringBasis` field, each with different offset management approaches.

## Rostering Basis

### `"demandBased"` (Default)
**Philosophy**: "Start with demand, find optimal employees"

```json
{
  "rosteringBasis": "demandBased",
  "fixedRotationOffset": "auto"
}
```

**Workflow**:
1. Start with demand requirements
2. Run ICPMP preprocessing (filters 303 → 16 employees)
3. Auto-distribute offsets across filtered employees
4. Solve to minimize employee count

**Use when**:
- ✅ You want the solver to find minimum employees needed
- ✅ ICPMP optimization is desired
- ✅ Standard workforce planning scenarios

**Valid offset modes**: `"auto"`, `"solverOptimized"`

---

### `"outcomeBased"` 
**Philosophy**: "I already know which teams/OUs work, assign them optimally"

```json
{
  "rosteringBasis": "outcomeBased",
  "fixedRotationOffset": "ouOffsets",
  "ouOffsets": [
    {"ouId": "ATSU OPS OFFICE", "rotationOffset": 0},
    {"ouId": "ATSU T1 LSU A1", "rotationOffset": 1}
  ]
}
```

**Workflow**:
1. Start with pre-determined OUs
2. **Skip ICPMP preprocessing** (use all employees)
3. Apply OU-based offsets
4. Solve to distribute work optimally

**Use when**:
- ✅ OUs are pre-assigned to work
- ✅ Manual control over which teams work
- ✅ OU-level rotation synchronization required

**Valid offset modes**: `"ouOffsets"` only

**Key Differences from demandBased**:
- ❌ No ICPMP filtering (uses all employees matching rank/product/scheme)
- ❌ No employee count optimization
- ❌ No `enableOtAwareIcpmp` support
- ✅ Full control over offset distribution via OUs

---

## Offset Modes

### Validation Rules

**Valid Combinations**:
| rosteringBasis | Valid fixedRotationOffset | ICPMP Runs? |
|----------------|---------------------------|-------------|
| `demandBased` | `auto`, `solverOptimized` | ✅ Yes |
| `outcomeBased` | `ouOffsets` | ❌ No |

**Invalid Combinations** (will raise error):
- ❌ `demandBased` + `ouOffsets`
- ❌ `outcomeBased` + `auto`
- ❌ `outcomeBased` + `solverOptimized`

---

## Supported Modes

### 1. `"auto"` (Recommended for demandBased)
**Sequential staggering** - Distributes employees evenly across offset values (0, 1, 2, ...).

```json
{
  "fixedRotationOffset": "auto",
  "demandItems": [{
    "requirements": [{
      "workPattern": ["D", "D", "D", "D", "D", "D", "D", "D", "O"]
    }]
  }],
  "employees": [
    {"employeeId": "E001", "rotationOffset": 0},
    {"employeeId": "E002", "rotationOffset": 0}
  ]
}
```

**Result**: Employees automatically assigned offsets 0, 1, 2, 3, 4, 5, 6, 7, 8, 0, 1, ...

**Use when**:
- ✅ You want automatic, balanced offset distribution
- ✅ Production rosters with standard patterns
- ✅ Fast solving with predictable results

---

### 2. `"ouOffsets"` 
**OU-level offsets** - All members of an Organizational Unit (OU) share the same rotation offset.

```json
{
  "fixedRotationOffset": "ouOffsets",
  "ouOffsets": [
    {"ouId": "ATSU OPS OFFICE", "rotationOffset": 0},
    {"ouId": "ATSU T1 LSU A1", "rotationOffset": 3},
    {"ouId": "ATSU T1 LSU A2", "rotationOffset": 6}
  ],
  "demandItems": [{
    "requirements": [{
      "workPattern": ["D", "D", "D", "D", "D", "D", "D", "D", "O"]
    }]
  }],
  "employees": [
    {"employeeId": "E001", "ouId": "ATSU OPS OFFICE"},
    {"employeeId": "E002", "ouId": "ATSU OPS OFFICE"},
    {"employeeId": "E003", "ouId": "ATSU T1 LSU A1"}
  ]
}
```

**Result**:
- All ATSU OPS OFFICE members → offset 0
- All ATSU T1 LSU A1 members → offset 3
- All ATSU T1 LSU A2 members → offset 6

**Use when**:
- ✅ OUs need synchronized schedules
- ✅ OU-based rotation alignment is required
- ✅ Operational requirements dictate OU-level planning

**Validation Rules**:
- ❌ ERROR if `ouOffsets` array missing
- ⚠️ WARNING if employee's OU not in `ouOffsets` (uses rotationOffset=0)
- ❌ ERROR if offset outside range [0, cycle_length-1]

---

### 3. `"solverOptimized"` (Advanced)
**Solver decides** - CP-SAT optimizer chooses best offsets dynamically.

```json
{
  "fixedRotationOffset": "solverOptimized",
  "employees": [
    {"employeeId": "E001", "rotationOffset": 0},
    {"employeeId": "E002", "rotationOffset": 0}
  ]
}
```

**Result**: Solver creates offset decision variables and optimizes assignments + offsets simultaneously.

**Use when**:
- ✅ Exploring new patterns
- ✅ Research/testing different offset distributions
- ⚠️ SLOWER solve times (more variables to optimize)

---

## Backward Compatibility

Old boolean format automatically converts:

| Old Format | New Format |
|------------|------------|
| `"fixedRotationOffset": true` | `"auto"` |
| `"fixedRotationOffset": false` | `"solverOptimized"` |

**Example**:
```json
// Old input
{
  "fixedRotationOffset": true
}

// Automatically converted to
{
  "fixedRotationOffset": "auto"
}
```

---

## Validation & Error Handling

### OU Offsets Validation

**Error 1: Missing ouOffsets array**
```json
{
  "fixedRotationOffset": "ouOffsets"
  // Missing ouOffsets array!
}
```
**Error**: `"fixedRotationOffset='ouOffsets' requires 'ouOffsets' array in input"`

---

**Error 2: Employee OU not in array (Warning only)**
```json
{
  "fixedRotationOffset": "ouOffsets",
  "ouOffsets": [
    {"ouId": "ATSU OPS OFFICE", "rotationOffset": 0}
  ],
  "employees": [
    {"employeeId": "E001", "ouId": "ATSU T1 LSU A1"}  // Not in ouOffsets!
  ]
}
```
**Warning**: `"Employee 'E001' has OU 'ATSU T1 LSU A1' not found in ouOffsets array - will use rotationOffset=0"`

---

**Error 3: Offset out of range**
```json
{
  "fixedRotationOffset": "ouOffsets",
  "ouOffsets": [
    {"ouId": "ATSU OPS OFFICE", "rotationOffset": 10}  // Pattern has 9-day cycle!
  ],
  "demandItems": [{
    "requirements": [{
      "workPattern": ["D","D","D","D","D","D","D","D","O"]  // 9 days
    }]
  }]
}
```
**Error**: `"OU 'ATSU OPS OFFICE' offset 10 out of range [0, 8] for cycle length 9"`

---

## Comparison Table

| Feature | auto | ouOffsets | solverOptimized |
|---------|------|-----------|-----------------|
| **Speed** | ⚡ Fast | ⚡ Fast | 🐌 Slow |
| **Setup** | ✅ Zero config | 📋 Define OUs | ✅ Zero config |
| **OU Sync** | ❌ No | ✅ Yes | ❌ No |
| **Flexibility** | ⚖️ Medium | ⚖️ Low (fixed) | 🔄 High |
| **Deterministic** | ✅ Yes | ✅ Yes | ❌ No |
| **Use Case** | Production | OU-based ops | Research |

---

## Migration Guide

### From Boolean to String

**Before (v0.95 and earlier)**:
```json
{
  "fixedRotationOffset": true
}
```

**After (v0.96+)** - Both work, but string recommended:
```json
{
  "fixedRotationOffset": "auto"  // Explicit and clear
}
```

---

### Enabling OU-Based Offsets

**Step 1**: Change mode
```json
{
  "fixedRotationOffset": "ouOffsets"
}
```

**Step 2**: Add `ouOffsets` array
```json
{
  "ouOffsets": [
    {"ouId": "ATSU OPS OFFICE", "rotationOffset": 0},
    {"ouId": "ATSU T1 LSU A1", "rotationOffset": 3}
  ]
}
```

**Step 3**: Ensure all employees have `ouId`
```json
{
  "employees": [
    {"employeeId": "E001", "ouId": "ATSU OPS OFFICE"},
    {"employeeId": "E002", "ouId": "ATSU T1 LSU A1"}
  ]
}
```

---

## Testing

Run test suite:
```bash
python test_offset_modes.py
```

Expected output:
```
✅ PASS: Normalize Values
✅ PASS: Auto Mode  
✅ PASS: OU Offsets (Valid)
✅ PASS: OU Offsets (Missing OU)
✅ PASS: OU Offsets (Invalid Range)
✅ PASS: Backward Compatibility

✅ ALL TESTS PASSED!
```

---

## API Integration

All three endpoints support the new format:

**POST /solve (Sync)**
```bash
curl -X POST http://localhost:8080/solve \
  -H "Content-Type: application/json" \
  -d '{
    "fixedRotationOffset": "ouOffsets",
    "ouOffsets": [...]
  }'
```

**POST /solve/async**
```bash
curl -X POST http://localhost:8080/solve/async \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "fixedRotationOffset": "auto",
      ...
    }
  }'
```

---

## Troubleshooting

### Issue: "Team 'X' not found in teamOffsets array"
**Solution**: Add missing team to `teamOffsets` array with valid offset (0 to cycle_length-1)

### Issue: "Offset out of range"
**Solution**: Check pattern cycle length. For 9-day pattern [D,D,D,D,D,D,D,D,O], valid offsets are 0-8.

### Issue: Solver taking too long
**Solution**: Change from `"solverOptimized"` to `"auto"` for faster solving.

### Issue: Want teams on same schedule
**Solution**: Use `"teamOffsets"` mode and assign same offset to those teams.

---

## Schema Version

This feature is available in **schema version 0.96+**.

Update your input JSON:
```json
{
  "schemaVersion": "0.96",
  "fixedRotationOffset": "auto"  // or "teamOffsets" or "solverOptimized"
}
```

---

## Examples

### Example 1: Auto Mode (Production)
```json
{
  "schemaVersion": "0.96",
  "fixedRotationOffset": "auto",
  "demandItems": [{
    "requirements": [{
      "workPattern": ["D", "D", "D", "D", "D", "O", "O"],
      "headcount": 10
    }]
  }],
  "employees": [...]
}
```

### Example 2: Team Offsets (3 Teams)
```json
{
  "schemaVersion": "0.96",
  "fixedRotationOffset": "teamOffsets",
  "teamOffsets": [
    {"teamId": "TM-Morning", "rotationOffset": 0},
    {"teamId": "TM-Evening", "rotationOffset": 2},
    {"teamId": "TM-Night", "rotationOffset": 4}
  ],
  "employees": [
    {"employeeId": "E001", "teamId": "TM-Morning"},
    {"employeeId": "E002", "teamId": "TM-Evening"}
  ]
}
```

### Example 3: Solver Optimized (Research)
```json
{
  "schemaVersion": "0.96",
  "fixedRotationOffset": "solverOptimized",
  "solverRunTime": {"maxSeconds": 600},  // Allow more time
  "employees": [...]
}
```
