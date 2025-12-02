# Automatic Rotation Offset Management

## Overview

The NGRS Solver now automatically manages employee rotation offsets to ensure proper coverage when using pattern-based scheduling with off days (`O` in work patterns).

## Problem

When using a work pattern like `["D", "D", "N", "N", "O", "O"]` with `fixedRotationOffset: true`:
- **Without staggered offsets**: If all employees have `rotationOffset: 0`, they're all on the same day of the pattern cycle
- **Result**: On "O" (off) days, NO employees are available to work → INFEASIBLE solution
- **Example**: All employees have O days on Sept 5-6, 11-12, 17-18, etc. → Cannot fill shifts on those dates

## Solution

The solver automatically staggers employee rotation offsets across the pattern cycle (0-5 for a 6-day pattern):
- **Offset 0**: 14-15 employees on days 0-5 of their pattern
- **Offset 1**: 14-15 employees on days 1-6 of their pattern (shifted by 1 day)
- **Offset 2-5**: Similar distribution
- **Result**: On any calendar day, some employees are on D days, some on N days, some on O days → Full coverage achieved

## When It Activates

The offset manager automatically runs when:
1. `fixedRotationOffset: true` (uses pre-assigned offsets)
2. Work pattern contains `'O'` days (off days in the pattern)
3. Input has employees to process

**If `fixedRotationOffset: false`**, the solver optimizes offsets itself and staggering is skipped.

## API Integration

### Automatic (Default Behavior)

The offset manager is **automatically applied** to all solve requests:

```bash
# Sync endpoint
POST /solve
Content-Type: application/json

{
  "fixedRotationOffset": true,
  "demandItems": [{
    "requirements": [{
      "workPattern": ["D", "D", "N", "N", "O", "O"],
      "headcount": 10
    }]
  }],
  "employees": [
    {"employeeId": "EMP001", "rotationOffset": 0},
    {"employeeId": "EMP002", "rotationOffset": 0},
    ...
  ]
}
```

**Server automatically**:
1. Detects O-pattern and `fixedRotationOffset: true`
2. Distributes offsets: EMP001→0, EMP002→1, EMP003→2, EMP004→3, EMP005→4, EMP006→5, EMP007→0, ...
3. Proceeds with solving

### Async Endpoint

Same automatic behavior applies:

```bash
POST /solve/async
Content-Type: application/json

{
  "input_json": { ...NGRS input with O-pattern... },
  "priority": 5
}
```

Offset staggering happens **before** queuing the job.

## Standalone Usage

### Command Line

```bash
# Check and fix an input file
python -m src.offset_manager input/my_input.json --save

# Check only (no modifications)
python -m src.offset_manager input/my_input.json
```

### Python API

```python
from src.offset_manager import ensure_staggered_offsets, validate_offset_configuration

# Load your input data
with open('input.json') as f:
    input_data = json.load(f)

# Validate before
is_valid, issues = validate_offset_configuration(input_data)
if not is_valid:
    print("Issues found:", issues)

# Apply staggering
input_data = ensure_staggered_offsets(input_data)

# Validate after
is_valid, issues = validate_offset_configuration(input_data)
print("Valid:", is_valid)
```

## Verification Script

Use the included verification script to check input files:

```bash
python3 verify_input.py input/input_v0.8_0212_1300.json
```

Output shows:
- Configuration details
- Offset distribution
- Validation checks
- Issues and recommendations

## Example: Before & After

### Before (All offsets at 0)
```json
{
  "fixedRotationOffset": true,
  "employees": [
    {"employeeId": "EMP001", "rotationOffset": 0},
    {"employeeId": "EMP002", "rotationOffset": 0},
    {"employeeId": "EMP003", "rotationOffset": 0},
    ...86 employees all at offset 0
  ]
}
```

**Problem**: All employees on same pattern day → O-days have no coverage → INFEASIBLE

### After (Automatically staggered)
```json
{
  "fixedRotationOffset": true,
  "employees": [
    {"employeeId": "EMP001", "rotationOffset": 0},
    {"employeeId": "EMP002", "rotationOffset": 1},
    {"employeeId": "EMP003", "rotationOffset": 2},
    {"employeeId": "EMP004", "rotationOffset": 3},
    {"employeeId": "EMP005", "rotationOffset": 4},
    {"employeeId": "EMP006", "rotationOffset": 5},
    {"employeeId": "EMP007", "rotationOffset": 0},
    ...distribution across 0-5
  ]
}
```

**Result**: Employees staggered across pattern → Every day has coverage → OPTIMAL solution

## Logging

The offset manager logs its actions:

```
OFFSET MANAGER: Checking rotation offsets
Found O-pattern in requirement 25_1 - staggering needed
Current offset distribution: {0: 86}
Detected pattern cycle length: 6 from ['D', 'D', 'N', 'N', 'O', 'O']
Applying staggered offsets across 6 values...
New offset distribution: {0: 15, 1: 15, 2: 14, 3: 14, 4: 14, 5: 14}
✓ Updated 71 employees
```

## Configuration

No configuration needed - it works automatically!

However, you can control it programmatically:

```python
# Force staggering even if criteria not met
ensure_staggered_offsets(input_data, force=True)

# Skip staggering for this request (set fixedRotationOffset=false)
input_data['fixedRotationOffset'] = False
```

## Production Deployment

### Docker/AppRunner

The offset manager is **built into the API server** - no additional setup needed.

When deploying:
1. Pull latest code with offset manager
2. Restart services
3. All API requests automatically benefit from offset management

### Manual Files

If uploading input files directly to the server:

```bash
# On server
cd /path/to/ngrssolver
python -m src.offset_manager input/my_input.json --save
python src/run_solver.py --in input/my_input.json --time 120
```

## Troubleshooting

### Still getting INFEASIBLE with O-patterns?

Check:
1. **fixedRotationOffset**: Must be `true`
2. **Run verification**: `python3 verify_input.py input/your_file.json`
3. **Check offsets**: Are they staggered (0-5) or all the same?
4. **API vs File**: If using API, offsets are auto-managed. If running locally, ensure file has staggered offsets.

### Offsets not being staggered?

Check logs for:
- "fixedRotationOffset is false - no staggering needed" → Set to `true`
- "No O-patterns found" → Pattern must contain `'O'` days
- "Offsets already staggered - no changes needed" → Already correct

### Want to disable automatic staggering?

Set `fixedRotationOffset: false` - solver will optimize offsets instead.

## Files

- **src/offset_manager.py**: Core module
- **verify_input.py**: Verification script
- **test_offset_manager.py**: Unit tests
- **src/api_server.py**: API integration (lines 44, 335, 690)

## Summary

✅ **Automatic**: Works without configuration  
✅ **Intelligent**: Only activates when needed  
✅ **Safe**: Validates before and after  
✅ **Logged**: Full visibility into changes  
✅ **Production-Ready**: Integrated into API server
