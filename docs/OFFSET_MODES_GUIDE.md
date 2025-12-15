# Fixed Rotation Offset Modes - User Guide

## Overview

The `fixedRotationOffset` field now supports **string-based modes** for flexible offset management. This change provides better control over how employee rotation offsets are assigned.

## Supported Modes

### 1. `"auto"` (Recommended for Production)
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

### 2. `"teamOffsets"` (New!)
**Team-level offsets** - All members of a team share the same rotation offset.

```json
{
  "fixedRotationOffset": "teamOffsets",
  "teamOffsets": [
    {"teamId": "TM-Alpha", "rotationOffset": 0},
    {"teamId": "TM-Bravo", "rotationOffset": 3},
    {"teamId": "TM-Charlie", "rotationOffset": 6}
  ],
  "demandItems": [{
    "requirements": [{
      "workPattern": ["D", "D", "D", "D", "D", "D", "D", "D", "O"]
    }]
  }],
  "employees": [
    {"employeeId": "E001", "teamId": "TM-Alpha"},
    {"employeeId": "E002", "teamId": "TM-Alpha"},
    {"employeeId": "E003", "teamId": "TM-Bravo"}
  ]
}
```

**Result**:
- All TM-Alpha members → offset 0
- All TM-Bravo members → offset 3
- All TM-Charlie members → offset 6

**Use when**:
- ✅ Teams need synchronized schedules
- ✅ Team-based rotation alignment is required
- ✅ Operational requirements dictate team-level planning

**Validation Rules**:
- ❌ ERROR if `teamOffsets` array missing
- ❌ ERROR if employee's team not in `teamOffsets`
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

### Team Offsets Validation

**Error 1: Missing teamOffsets array**
```json
{
  "fixedRotationOffset": "teamOffsets"
  // Missing teamOffsets array!
}
```
**Error**: `"fixedRotationOffset='teamOffsets' requires 'teamOffsets' array in input"`

---

**Error 2: Employee team not in array**
```json
{
  "fixedRotationOffset": "teamOffsets",
  "teamOffsets": [
    {"teamId": "TM-A", "rotationOffset": 0}
  ],
  "employees": [
    {"employeeId": "E001", "teamId": "TM-B"}  // TM-B not in teamOffsets!
  ]
}
```
**Error**: `"Employee 'E001' has team 'TM-B' not found in teamOffsets array"`

---

**Error 3: Offset out of range**
```json
{
  "fixedRotationOffset": "teamOffsets",
  "teamOffsets": [
    {"teamId": "TM-A", "rotationOffset": 10}  // Pattern has 9-day cycle!
  ],
  "demandItems": [{
    "requirements": [{
      "workPattern": ["D","D","D","D","D","D","D","D","O"]  // 9 days
    }]
  }]
}
```
**Error**: `"Team 'TM-A' offset 10 out of range [0, 8] for cycle length 9"`

---

## Comparison Table

| Feature | auto | teamOffsets | solverOptimized |
|---------|------|-------------|-----------------|
| **Speed** | ⚡ Fast | ⚡ Fast | 🐌 Slow |
| **Setup** | ✅ Zero config | 📋 Define teams | ✅ Zero config |
| **Team Sync** | ❌ No | ✅ Yes | ❌ No |
| **Flexibility** | ⚖️ Medium | ⚖️ Low (fixed) | 🔄 High |
| **Deterministic** | ✅ Yes | ✅ Yes | ❌ No |
| **Use Case** | Production | Team-based ops | Research |

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

### Enabling Team-Based Offsets

**Step 1**: Change mode
```json
{
  "fixedRotationOffset": "teamOffsets"
}
```

**Step 2**: Add `teamOffsets` array
```json
{
  "teamOffsets": [
    {"teamId": "TM-Alpha", "rotationOffset": 0},
    {"teamId": "TM-Bravo", "rotationOffset": 3}
  ]
}
```

**Step 3**: Ensure all employees have `teamId`
```json
{
  "employees": [
    {"employeeId": "E001", "teamId": "TM-Alpha"},
    {"employeeId": "E002", "teamId": "TM-Bravo"}
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
✅ PASS: Team Offsets (Valid)
✅ PASS: Team Offsets (Missing Team)
✅ PASS: Team Offsets (Invalid Range)
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
    "fixedRotationOffset": "teamOffsets",
    "teamOffsets": [...]
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
