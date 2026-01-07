# NGRS Solver Output Schema v0.95

**CRITICAL**: This is the canonical output format. ALL solver modes MUST produce this exact structure.

## Version History
- **v0.95** (Jan 2026): Standardized output across all modes
  - Fixed: OFF_DAY status (was 'OFF' in CP-SAT mode)
  - Fixed: OFF_DAY timing (was null, now includes shift times)
  - Fixed: UNASSIGNED timing (was null, now includes shift times)

## Solver Modes Coverage
This schema applies to ALL rostering modes:
- ✅ Demand-based (incremental validation)
- ✅ Outcome-based (CP-SAT template mode)
- ✅ Outcome-based (incremental slot filling)
- ✅ Template roster mode

---

## Top-Level Structure

```json
{
  "schemaVersion": "0.95",
  "planningReference": "<string>",
  "publicHolidays": [...],
  "solverRun": {...},
  "score": {...},
  "scoreBreakdown": {...},
  "assignments": [...],          // PRIMARY OUTPUT: All work/off/unassigned records
  "employeeRoster": [...],       // Employee-centric view with daily status
  "rosterSummary": {...},
  "solutionQuality": {...},
  "unmetDemand": [...],
  "meta": {...}
}
```

---

## 1. assignments (Array)

**Purpose**: Primary output - all scheduling records for all employees

**Record Types** (by `status` field):
- `ASSIGNED` - Work shift assigned to employee
- `OFF_DAY` - Rest day (pattern position 'O')
- `UNASSIGNED` - Slot could not be filled (constraint violations or no eligible employees)

### Common Fields (ALL record types)

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `assignmentId` | string | ✅ | Unique assignment identifier | `"DI-xxx-2026-01-01-D-00012345"` |
| `slotId` | string | ✅ | Slot/demand identifier | `"DI-xxx-169_1-D-2026-01-01"` |
| `employeeId` | string | ✅ (null for UNASSIGNED) | Employee ID | `"00012345"` |
| `demandId` | string | ✅ | Demand item ID | `"DI-2512170306-55151724"` |
| `requirementId` | string | ✅ | Work requirement ID | `"169_1"` |
| `date` | string | ✅ | Date in ISO format | `"2026-01-15"` |
| `shiftCode` | string | ✅ | Shift code | `"D"`, `"N"`, `"E"`, `"O"` |
| `startDateTime` | string | ✅ | Shift start time (ISO 8601) | `"2026-01-15T08:00:00"` |
| `endDateTime` | string | ✅ | Shift end time (ISO 8601) | `"2026-01-15T20:00:00"` |
| `status` | string | ✅ | Assignment status | `"ASSIGNED"`, `"OFF_DAY"`, `"UNASSIGNED"` |
| `hours` | object | ✅ | Hour breakdown | See Hours Object below |

**CRITICAL RULES**:
1. `startDateTime` and `endDateTime` MUST NEVER be `null` - even for OFF_DAY and UNASSIGNED
2. Use shift timing from demand/shift details for context
3. `status` values are standardized - DO NOT use aliases like 'OFF' or 'REST'

### Hours Object (ALL record types)

```json
{
  "gross": 12.0,      // Total shift duration
  "lunch": 1.0,       // Lunch break (unpaid)
  "normal": 8.8,      // Normal hours (MOM-compliant)
  "ot": 2.2,          // Overtime hours
  "restDayPay": 0.0,  // Rest day pay (APO Scheme A 6th day)
  "paid": 12.0        // Total paid hours (gross for work shifts)
}
```

For OFF_DAY and UNASSIGNED: All values should be `0.0`

---

## 2. ASSIGNED Records

Work shifts successfully assigned to employees.

### Example
```json
{
  "assignmentId": "DI-2512170306-55151724-2026-01-15-D-00012345",
  "slotId": "DI-2512170306-55151724-169_1-D-2026-01-15",
  "employeeId": "00012345",
  "demandId": "DI-2512170306-55151724",
  "requirementId": "169_1",
  "date": "2026-01-15",
  "shiftCode": "D",
  "startDateTime": "2026-01-15T08:00:00",
  "endDateTime": "2026-01-15T20:00:00",
  "status": "ASSIGNED",
  "hours": {
    "gross": 12.0,
    "lunch": 1.0,
    "normal": 8.8,
    "ot": 2.2,
    "restDayPay": 0.0,
    "paid": 12.0
  }
}
```

---

## 3. OFF_DAY Records

Rest days according to employee work pattern.

### Key Points
- ✅ `shiftCode` = `"O"`
- ✅ `status` = `"OFF_DAY"` (NOT 'OFF', 'REST', or other aliases)
- ✅ `startDateTime` and `endDateTime` MUST have shift times (for UI context)
- ✅ `employeeId` is populated (not null)
- ✅ All `hours` fields are `0.0`

### Example
```json
{
  "assignmentId": "DI-2512170306-55151724-2026-01-06-O-00012345",
  "slotId": "DI-2512170306-55151724-169_1-O-2026-01-06",
  "employeeId": "00012345",
  "demandId": "DI-2512170306-55151724",
  "requirementId": "169_1",
  "date": "2026-01-06",
  "shiftCode": "O",
  "startDateTime": "2026-01-06T08:00:00",
  "endDateTime": "2026-01-06T20:00:00",
  "status": "OFF_DAY",
  "hours": {
    "gross": 0.0,
    "lunch": 0.0,
    "net": 0.0,
    "normal": 0.0,
    "ot": 0.0,
    "ph": 0.0,
    "restDayPay": 0.0,
    "paid": 0.0
  }
}
```

---

## 4. UNASSIGNED Records

Slots that could not be filled due to constraints or lack of eligible employees.

### Key Points
- ✅ `employeeId` = `null`
- ✅ `status` = `"UNASSIGNED"`
- ✅ `startDateTime` and `endDateTime` MUST have shift times
- ✅ `shiftCode` reflects the shift type (D/N/E)
- ✅ Optional: `reason` field explaining why slot is unassigned
- ✅ All `hours` fields are `0.0`

### Example
```json
{
  "assignmentId": "DI-2512170306-55151724-2026-01-10-D-UNASSIGNED",
  "slotId": "DI-2512170306-55151724-169_1-D-2026-01-10",
  "employeeId": null,
  "demandId": "DI-2512170306-55151724",
  "requirementId": "169_1",
  "date": "2026-01-10",
  "shiftCode": "D",
  "startDateTime": "2026-01-10T08:00:00",
  "endDateTime": "2026-01-10T20:00:00",
  "status": "UNASSIGNED",
  "reason": "No eligible employees available (constraints or unavailability)",
  "hours": {
    "gross": 0.0,
    "lunch": 0.0,
    "net": 0.0,
    "normal": 0.0,
    "ot": 0.0,
    "ph": 0.0,
    "restDayPay": 0.0,
    "paid": 0.0
  }
}
```

---

## 5. employeeRoster (Array)

**Purpose**: Employee-centric view showing daily status for each employee across the planning period.

### Structure
```json
{
  "employeeId": "00012345",
  "rankId": "SO2",
  "productTypeId": "APO",
  "ouId": "ATSU T1 LSU A1",
  "scheme": "A",
  "rotationOffset": 0,
  "workPattern": ["D","D","D","D","D","O","O"],
  "totalDays": 31,
  "workDays": 22,
  "offDays": 9,
  "normalHours": 193.6,
  "otHours": 48.4,
  "totalHours": 242.0,
  "assignedDays": 22,
  "unassignedDays": 0,
  "dailyStatus": [
    {
      "date": "2026-01-01",
      "status": "ASSIGNED",
      "shiftCode": "D",
      "patternDay": 0,
      "assignmentId": "DI-xxx-2026-01-01-D-00012345",
      "startDateTime": "2026-01-01T08:00:00",
      "endDateTime": "2026-01-01T20:00:00"
    },
    {
      "date": "2026-01-06",
      "status": "OFF_DAY",
      "shiftCode": "O",
      "patternDay": 5,
      "assignmentId": "DI-xxx-2026-01-06-O-00012345",
      "startDateTime": "2026-01-06T08:00:00",
      "endDateTime": "2026-01-06T20:00:00"
    }
  ]
}
```

### dailyStatus Records

| Field | Type | Description |
|-------|------|-------------|
| `date` | string | Date in ISO format |
| `status` | string | One of: `ASSIGNED`, `OFF_DAY`, `UNASSIGNED`, `NOT_USED` |
| `shiftCode` | string | Shift code: D/N/E/O |
| `patternDay` | number | Position in work pattern (0 to pattern length-1) |
| `assignmentId` | string | Link to assignment record |
| `startDateTime` | string | Shift start time (MUST be populated) |
| `endDateTime` | string | Shift end time (MUST be populated) |

---

## Implementation Guidelines

### For All Solver Modes

When creating output records, follow these rules:

#### 1. Status Values
```python
# ✅ CORRECT
status = "OFF_DAY"
status = "ASSIGNED"
status = "UNASSIGNED"

# ❌ WRONG - DO NOT USE
status = "OFF"       # Use OFF_DAY
status = "REST"      # Use OFF_DAY
status = "EMPTY"     # Use UNASSIGNED
```

#### 2. DateTime Fields
```python
# ✅ CORRECT - Always include timing
assignment = {
    "startDateTime": f"{date_str}T{shift_start}",
    "endDateTime": f"{date_str}T{shift_end}",
    "status": "OFF_DAY"  # Even for OFF days!
}

# ❌ WRONG - Never use null
assignment = {
    "startDateTime": None,  # WRONG!
    "endDateTime": None,    # WRONG!
}
```

#### 3. Hours Object
```python
# For work shifts (ASSIGNED)
hours = calculate_mom_compliant_hours(...)

# For OFF_DAY and UNASSIGNED
hours = {
    "gross": 0.0,
    "lunch": 0.0,
    "net": 0.0,
    "normal": 0.0,
    "ot": 0.0,
    "ph": 0.0,
    "restDayPay": 0.0,
    "paid": 0.0
}
```

---

## Files That Create Output Records

### Assignment Creation
- `context/engine/cpsat_template_generator.py` - CP-SAT outcome-based mode
- `context/engine/outcome_based_with_slots.py` - Incremental outcome-based mode
- `context/engine/template_roster.py` - Template roster mode
- `context/engine/solver_engine.py` - Demand-based mode

### Output Building
- `src/output_builder.py` - Builds final output structure
- `src/output_builder_async.py` - Async mode output building

**All these files MUST follow this schema exactly.**

---

## Validation Checklist

Before deploying changes that affect output:

- [ ] `status` values match exactly: `ASSIGNED`, `OFF_DAY`, `UNASSIGNED`
- [ ] `startDateTime` and `endDateTime` are NEVER null for any record type
- [ ] OFF_DAY records have `shiftCode` = `"O"`
- [ ] UNASSIGNED records have `employeeId` = `null`
- [ ] All `hours` objects have all required fields
- [ ] `employeeRoster` includes timing in `dailyStatus` records
- [ ] Test output from ALL solver modes (demand-based, outcome-based, template)

---

## Schema Version

Current: **v0.95**

Update this version number when making breaking changes to the output structure.

---

## Contact & Maintenance

For questions or proposed changes to this schema:
1. Review this document first
2. Check all solver mode implementations
3. Test with representative inputs from each mode
4. Update this document if schema changes are necessary
