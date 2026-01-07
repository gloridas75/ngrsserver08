# Output Format Specification v0.95

**Last Updated**: 2026-01-07  
**Schema Version**: 0.95  
**Applies To**: All rostering modes (Demand-based, Outcome-based/CP-SAT, Incremental)

---

## Overview

This document specifies the canonical output format for NGRS Solver v0.95. All rostering modes (demand-based, outcome-based, incremental) MUST produce outputs conforming to this specification.

**Critical Requirement**: ALL assignment types (ASSIGNED, OFF_DAY, UNASSIGNED) MUST include `startDateTime` and `endDateTime` fields with valid ISO 8601 timestamps. `null` values are NOT permitted.

---

## Top-Level Structure

```json
{
  "schemaVersion": "0.95",
  "planningReference": { ... },
  "solverRun": { ... },
  "score": { ... },
  "scoreBreakdown": { ... },
  "assignments": [ ... ],
  "employeeRoster": { ... },
  "rosterSummary": { ... },
  "solutionQuality": { ... },
  "unmetDemand": [ ... ],
  "meta": { ... }
}
```

### Required Top-Level Keys

| Key | Type | Description | Required |
|-----|------|-------------|----------|
| `schemaVersion` | string | Must be "0.95" | ✅ |
| `planningReference` | object | Planning period metadata | ✅ |
| `solverRun` | object | Solver execution details | ✅ |
| `score` | object | Overall solution score | ✅ |
| `scoreBreakdown` | object | Detailed scoring by constraint | ✅ |
| `assignments` | array | Flat list of all assignments | ✅ |
| `employeeRoster` | object | Employee-keyed roster structure | ✅ |
| `rosterSummary` | object | Statistical summary | ✅ |
| `solutionQuality` | object | Solution quality metrics | ✅ |
| `unmetDemand` | array | Slots with insufficient coverage | ✅ |
| `meta` | object | Rostering mode and configuration | ✅ |

---

## Assignment Object Specification

### Status Values

Three valid status values:

1. **`ASSIGNED`** - Employee assigned to work a shift
2. **`OFF_DAY`** - Employee's rest day/OFF day within rotation pattern
3. **`UNASSIGNED`** - Slot exists but no employee assigned

**Historical Note**: Status value `"OFF"` was used in earlier versions but is **DEPRECATED** as of v0.95. All code should use `"OFF_DAY"` consistently.

---

### Common Fields (All Status Types)

All assignments MUST include these fields regardless of status:

```json
{
  "assignmentId": "string (UUID)",
  "employeeId": "string",
  "status": "ASSIGNED | OFF_DAY | UNASSIGNED",
  "date": "YYYY-MM-DD",
  "shiftCode": "string",
  "startDateTime": "YYYY-MM-DDTHH:mm:ss",  // NEVER null
  "endDateTime": "YYYY-MM-DDTHH:mm:ss"      // NEVER null
}
```

**Critical Timing Requirements**:
- `startDateTime` and `endDateTime` MUST contain valid ISO 8601 timestamps
- `null` values are NOT permitted for any assignment type
- For OFF_DAY: Use the shift timing that would have been worked (provides UI context)
- For UNASSIGNED: Use the slot's shift timing
- For ASSIGNED: Use the actual work shift timing

---

### ASSIGNED Status

Full assignment of employee to work shift.

**Required Fields**:
```json
{
  "assignmentId": "ASG-uuid",
  "employeeId": "EMP123",
  "status": "ASSIGNED",
  "date": "2026-01-15",
  "shiftCode": "D",
  "startDateTime": "2026-01-15T08:00:00",
  "endDateTime": "2026-01-15T20:00:00",
  "positionCode": "SO",
  "locationCode": "SITE-A",
  "originalSlotId": "SLOT-uuid",
  "normalHours": 12.0,
  "overtimeHours": 0.0,
  "publicHolidayHours": 0.0,
  "restDayPay": 0.0,
  "isPublicHoliday": false
}
```

**Field Descriptions**:

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `assignmentId` | string | Unique identifier (UUID) | ✅ |
| `employeeId` | string | Employee identifier | ✅ |
| `status` | string | Must be "ASSIGNED" | ✅ |
| `date` | string | Assignment date (YYYY-MM-DD) | ✅ |
| `shiftCode` | string | Shift code (D, N, E, etc.) | ✅ |
| `startDateTime` | string | Shift start (ISO 8601) | ✅ |
| `endDateTime` | string | Shift end (ISO 8601) | ✅ |
| `positionCode` | string | Position/rank code | ✅ |
| `locationCode` | string | Work location | ✅ |
| `originalSlotId` | string | Source demand slot UUID | ✅ |
| `normalHours` | number | Regular working hours | ✅ |
| `overtimeHours` | number | Overtime hours | ✅ |
| `publicHolidayHours` | number | Public holiday hours | ✅ |
| `restDayPay` | number | Rest day pay multiplier | ✅ |
| `isPublicHoliday` | boolean | Whether shift falls on PH | ✅ |

**Hour Calculation Notes**:
- Use `calculate_mom_compliant_hours()` from `context/engine/time_utils.py`
- Accounts for weekly/monthly OT caps
- Handles cross-midnight shifts
- Considers previous assignments in period

---

### OFF_DAY Status

Employee's scheduled rest day within rotation pattern.

**Required Fields**:
```json
{
  "assignmentId": "OFF-uuid",
  "employeeId": "EMP123",
  "status": "OFF_DAY",
  "date": "2026-01-16",
  "shiftCode": "O",
  "startDateTime": "2026-01-16T08:00:00",  // Shift timing for context
  "endDateTime": "2026-01-16T20:00:00",     // Not null!
  "positionCode": null,
  "locationCode": null,
  "originalSlotId": null,
  "normalHours": 0.0,
  "overtimeHours": 0.0,
  "publicHolidayHours": 0.0,
  "restDayPay": 0.0,
  "isPublicHoliday": false
}
```

**Critical Requirements**:
- `status` MUST be `"OFF_DAY"` (not "OFF")
- `shiftCode` MUST be `"O"`
- `startDateTime` and `endDateTime` MUST contain shift timing (not null)
- Timing should reflect the shift pattern the employee follows (e.g., 08:00-20:00 for day shift workers)
- Hours fields (normalHours, overtimeHours, etc.) MUST be `0.0`
- Optional fields (positionCode, locationCode, originalSlotId) should be `null`

**Implementation References**:
- Outcome-based mode: `context/engine/cpsat_template_generator.py:_create_off_day_assignment()`
- Demand-based mode: `src/output_builder.py` (lines 640-670)

---

### UNASSIGNED Status

Demand slot that could not be filled (insufficient coverage).

**Required Fields**:
```json
{
  "assignmentId": "UNASSIGNED-uuid",
  "employeeId": null,
  "status": "UNASSIGNED",
  "date": "2026-01-17",
  "shiftCode": "N",
  "startDateTime": "2026-01-17T20:00:00",  // Slot timing
  "endDateTime": "2026-01-18T08:00:00",    // Not null!
  "positionCode": "SO",
  "locationCode": "SITE-B",
  "originalSlotId": "SLOT-uuid",
  "normalHours": 0.0,
  "overtimeHours": 0.0,
  "publicHolidayHours": 0.0,
  "restDayPay": 0.0,
  "isPublicHoliday": false
}
```

**Critical Requirements**:
- `employeeId` MUST be `null`
- `startDateTime` and `endDateTime` MUST contain the slot's shift timing (not null)
- `positionCode` and `locationCode` come from the demand slot
- `originalSlotId` links to the unmet demand slot
- Hours fields MUST be `0.0`

**Implementation References**:
- Outcome-based: `context/engine/outcome_based_with_slots.py` (lines 770-785)
- Incremental: `context/engine/template_roster.py` (lines 856-890)

---

## Mode-Specific Characteristics

### Demand-Based Rostering

**File**: `src/output_builder.py`

**Characteristics**:
- No OFF_DAY records generated (only ASSIGNED and UNASSIGNED)
- Assigns employees to demand slots only
- UNASSIGNED records created for unmet demand
- `meta.rosteringBasis` = `"demand-based"`

**Example**: File 2 (RST-20260107-7DA65A9C) - 620 ASSIGNED assignments, no OFF_DAY

---

### Outcome-Based Rostering (CP-SAT)

**Files**: 
- `context/engine/cpsat_template_generator.py`
- `context/engine/outcome_based_with_slots.py`

**Characteristics**:
- Generates complete monthly templates with OFF_DAY records
- Groups employees by `ouId` for rotation offset handling
- Each OU gets unique template based on `rotationOffset`
- Creates OFF_DAY assignments with proper timing
- `meta.rosteringBasis` = `"outcome-based"`
- `meta.generationMode` = `"from_cpsat_template"`

**Example**: File 3 (RST-20260107-A7A59DEE) - 1748 ASSIGNED + 608 OFF_DAY assignments

**OFF_DAY Generation**:
```python
# From cpsat_template_generator.py:_create_off_day_assignment()
{
    "assignmentId": str(uuid.uuid4()),
    "employeeId": employee_id,
    "status": "OFF_DAY",  # Not "OFF"!
    "date": date_str,
    "shiftCode": "O",
    "startDateTime": shift_details.get('startTime'),  # Extract from pattern
    "endDateTime": shift_details.get('endTime'),      # Not null!
    "positionCode": None,
    "locationCode": None,
    # ... rest with 0.0/null values
}
```

---

### Incremental Mode

**File**: `context/engine/template_roster.py`

**Characteristics**:
- Updates existing roster with new demand
- Preserves existing assignments
- Creates UNASSIGNED for new unmet demand
- May have OFF_DAY from previous template generation
- `meta.rosteringBasis` varies based on previous mode

---

## Validation Checklist

Use this checklist to validate any NGRS Solver output:

### ✅ Schema Structure
- [ ] `schemaVersion` = "0.95"
- [ ] All 11 top-level keys present
- [ ] `assignments` is an array
- [ ] `employeeRoster` is an object

### ✅ Assignment Status Values
- [ ] Only uses: "ASSIGNED", "OFF_DAY", "UNASSIGNED"
- [ ] No "OFF" status values (deprecated)
- [ ] `shiftCode` = "O" for all OFF_DAY records

### ✅ Timing Requirements
- [ ] ALL assignments have `startDateTime` (never null)
- [ ] ALL assignments have `endDateTime` (never null)
- [ ] Timing format is ISO 8601 (YYYY-MM-DDTHH:mm:ss)
- [ ] OFF_DAY records have shift timing (not null)
- [ ] UNASSIGNED records have slot timing (not null)

### ✅ Hour Calculations
- [ ] ASSIGNED: normalHours + overtimeHours + publicHolidayHours > 0
- [ ] OFF_DAY: all hour fields = 0.0
- [ ] UNASSIGNED: all hour fields = 0.0
- [ ] No negative hour values

### ✅ Employee IDs
- [ ] ASSIGNED: employeeId present
- [ ] OFF_DAY: employeeId present
- [ ] UNASSIGNED: employeeId = null

### ✅ Shift Codes
- [ ] OFF_DAY always uses "O"
- [ ] ASSIGNED/UNASSIGNED use actual shift codes (D, N, E, etc.)

### ✅ Mode Consistency
- [ ] Demand-based: No OFF_DAY records expected
- [ ] Outcome-based: OFF_DAY records present with timing
- [ ] All modes produce same field structure

---

## Common Errors to Avoid

### ❌ Error 1: Null Timing in OFF_DAY
```json
// WRONG
{
  "status": "OFF_DAY",
  "startDateTime": null,  // ❌ Not allowed
  "endDateTime": null     // ❌ Not allowed
}

// CORRECT
{
  "status": "OFF_DAY",
  "startDateTime": "2026-01-16T08:00:00",  // ✅ Valid timing
  "endDateTime": "2026-01-16T20:00:00"     // ✅ Valid timing
}
```

**Fixed In**: Commit 7edd44e (2026-01-06)  
**File**: `context/engine/cpsat_template_generator.py`

---

### ❌ Error 2: Using "OFF" Status
```json
// WRONG
{
  "status": "OFF",  // ❌ Deprecated
  "shiftCode": "O"
}

// CORRECT
{
  "status": "OFF_DAY",  // ✅ Current standard
  "shiftCode": "O"
}
```

**Fixed In**: Commit 0fd204b (2026-01-06)  
**Files**: 
- `context/engine/cpsat_template_generator.py`
- `src/output_builder.py`

---

### ❌ Error 3: Null Timing in UNASSIGNED
```json
// WRONG
{
  "status": "UNASSIGNED",
  "startDateTime": null,  // ❌ Not allowed
  "endDateTime": null     // ❌ Not allowed
}

// CORRECT
{
  "status": "UNASSIGNED",
  "startDateTime": "2026-01-17T20:00:00",  // ✅ From slot
  "endDateTime": "2026-01-18T08:00:00"     // ✅ From slot
}
```

**Fixed In**: Commit 0fd204b (2026-01-06)  
**Files**:
- `context/engine/outcome_based_with_slots.py`
- `context/engine/template_roster.py`

---

### ❌ Error 4: Inconsistent OU Grouping
```json
// WRONG - Looking for wrong field
if 'organizationalUnitId' in employee:  // ❌ May not exist
    ou_id = employee['organizationalUnitId']

// CORRECT - Check both field names
ou_id = employee.get('ouId') or employee.get('organizationalUnitId')
```

**Fixed In**: Commit f5229b1 (2026-01-05)  
**File**: `context/engine/cpsat_template_generator.py`

---

## Testing & Validation

### Automated Validation Script

Location: `scripts/validate_output.py`

```bash
# Validate a single output file
python scripts/validate_output.py --file output/my_roster.json

# Validate all outputs in a directory
python scripts/validate_output.py --dir output/

# Strict mode (fail on any warning)
python scripts/validate_output.py --file output/my_roster.json --strict
```

### Manual Checks

```bash
# Check for null timing
jq '.assignments[] | select(.startDateTime == null or .endDateTime == null)' output.json

# Check for deprecated "OFF" status
jq '.assignments[] | select(.status == "OFF")' output.json

# Count assignments by status
jq '[.assignments[] | .status] | group_by(.) | map({status: .[0], count: length})' output.json

# Verify OFF_DAY has timing
jq '.assignments[] | select(.status == "OFF_DAY") | {date, startDateTime, endDateTime}' output.json | head -20
```

---

## Version History

| Version | Date | Changes | Commits |
|---------|------|---------|---------|
| 0.95 | 2026-01-07 | Initial specification documenting current format | - |
| - | 2026-01-06 | OFF_DAY timing fix (startDateTime/endDateTime not null) | 7edd44e |
| - | 2026-01-06 | Standardize OFF_DAY status (was "OFF") | 0fd204b |
| - | 2026-01-06 | UNASSIGNED timing fix | 0fd204b |
| - | 2026-01-05 | OU grouping fix (ouId vs organizationalUnitId) | f5229b1 |

---

## Contact & Support

For questions about this specification:
- Check `/context/glossary.md` for domain terminology
- See `/implementation_docs/CONSTRAINT_ARCHITECTURE.md` for architecture
- Review `/docs/RATIO_CACHING_GUIDE.md` for optimization details

**Last Verified Against**: 
- File 2: RST-20260107-7DA65A9C (demand-based, 620 assignments)
- File 3: RST-20260107-A7A59DEE (outcome-based, 2356 assignments with OFF_DAY)
