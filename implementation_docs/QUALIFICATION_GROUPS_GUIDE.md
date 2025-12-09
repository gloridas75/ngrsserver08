# Qualification Groups Feature - Complete Guide

## Overview

The qualification groups feature allows you to specify complex qualification requirements using OR logic, AND logic, or combinations of both. This provides flexibility for real-world scenarios where employees need certain qualifications but have alternatives for others.

## Problem Solved

**Before:** Only ALL logic was supported
```json
"requiredQualifications": ["FRISKING-LIC", "DETENTION-LIC", "XRAY-LIC"]
```
→ Employee MUST have all 3 licenses (no alternatives)

**After:** Support for OR and AND logic
```json
"requiredQualifications": [
  {
    "groupId": "screening",
    "matchType": "ANY",
    "qualifications": ["FRISKING-LIC", "XRAY-LIC"]
  },
  {
    "groupId": "custody",
    "matchType": "ALL",
    "qualifications": ["DETENTION-LIC"]
  }
]
```
→ Employee can use EITHER frisking OR X-ray, but MUST have detention

## Schema Format

### Option 1: Simple Array (Old Format - Still Supported)

```json
"requiredQualifications": ["QUAL1", "QUAL2", "QUAL3"]
```

**Behavior:**
- Employee must have ALL qualifications
- Automatically converted to single group with `matchType="ALL"`
- Fully backwards compatible

### Option 2: Qualification Groups (New Format)

```json
"requiredQualifications": [
  {
    "groupId": "group_name",
    "matchType": "ANY|ALL",
    "qualifications": ["QUAL1", "QUAL2"]
  }
]
```

**Fields:**
- `groupId` (string): Identifier for the group (for logging/debugging)
- `matchType` (string): "ALL" or "ANY"
  - `"ALL"`: Employee must have ALL qualifications in this group
  - `"ANY"`: Employee must have AT LEAST ONE qualification in this group
- `qualifications` (array): List of qualification codes

**Evaluation Logic:**
- Employee must satisfy ALL groups
- Within each group, matching is based on `matchType`

## Business Examples

### Example 1: Security Checkpoint

**Requirement:** Employee needs screening capability (frisking OR X-ray) AND custody authority (detention license)

```json
"requiredQualifications": [
  {
    "groupId": "screening_method",
    "matchType": "ANY",
    "qualifications": ["FRISKING-LIC", "XRAY-LIC"]
  },
  {
    "groupId": "custody_authority",
    "matchType": "ALL",
    "qualifications": ["DETENTION-LIC"]
  }
]
```

**Employee Matching:**
- ✅ EMP with: `[FRISKING-LIC, DETENTION-LIC]` → PASS (has frisking + detention)
- ✅ EMP with: `[XRAY-LIC, DETENTION-LIC]` → PASS (has X-ray + detention)
- ✅ EMP with: `[FRISKING-LIC, XRAY-LIC, DETENTION-LIC]` → PASS (has both screening + detention)
- ❌ EMP with: `[FRISKING-LIC]` → FAIL (missing detention)
- ❌ EMP with: `[DETENTION-LIC]` → FAIL (missing screening method)
- ❌ EMP with: `[FRISKING-LIC, XRAY-LIC]` → FAIL (missing detention)

### Example 2: Medical Response

**Requirement:** Medical qualification (nurse OR paramedic) AND basic life support (CPR)

```json
"requiredQualifications": [
  {
    "groupId": "medical_professional",
    "matchType": "ANY",
    "qualifications": ["NURSE-CERT", "PARAMEDIC-CERT"]
  },
  {
    "groupId": "basic_life_support",
    "matchType": "ALL",
    "qualifications": ["CPR-CERT"]
  }
]
```

### Example 3: Technical Support

**Requirement:** Technical expertise (network OR system) AND security clearance

```json
"requiredQualifications": [
  {
    "groupId": "technical_expertise",
    "matchType": "ANY",
    "qualifications": ["NETWORK-CERT", "SYSTEM-CERT"]
  },
  {
    "groupId": "access_control",
    "matchType": "ALL",
    "qualifications": ["SECURITY-CLEARANCE"]
  }
]
```

### Example 4: Multiple ANY Groups

**Requirement:** Language skill (English OR Mandarin) AND driving capability (car OR van license)

```json
"requiredQualifications": [
  {
    "groupId": "language",
    "matchType": "ANY",
    "qualifications": ["ENGLISH-PROF", "MANDARIN-PROF"]
  },
  {
    "groupId": "driving",
    "matchType": "ANY",
    "qualifications": ["CAR-LICENSE", "VAN-LICENSE"]
  }
]
```

**Employee Matching:**
- ✅ EMP with: `[ENGLISH-PROF, CAR-LICENSE]` → PASS
- ✅ EMP with: `[MANDARIN-PROF, VAN-LICENSE]` → PASS
- ✅ EMP with: `[ENGLISH-PROF, MANDARIN-PROF, CAR-LICENSE]` → PASS
- ❌ EMP with: `[ENGLISH-PROF]` → FAIL (no driving license)
- ❌ EMP with: `[CAR-LICENSE]` → FAIL (no language)

## Migration Guide

### For Existing Input Files

**No changes required!** Old format still works:

```json
// This still works exactly as before
"requiredQualifications": ["FRISKING-LIC", "DETENTION-LIC"]
```

### To Add OR Logic

1. Identify which qualifications are alternatives (OR)
2. Group them together with `matchType: "ANY"`
3. Keep mandatory qualifications in separate groups with `matchType: "ALL"`

**Before:**
```json
"requiredQualifications": ["FRISKING-LIC", "XRAY-LIC", "DETENTION-LIC"]
```

**After (if frisking and X-ray are alternatives):**
```json
"requiredQualifications": [
  {
    "groupId": "screening",
    "matchType": "ANY",
    "qualifications": ["FRISKING-LIC", "XRAY-LIC"]
  },
  {
    "groupId": "custody",
    "matchType": "ALL",
    "qualifications": ["DETENTION-LIC"]
  }
]
```

## Validation Rules

1. **Empty Groups:** Empty qualification groups are skipped (no error)
2. **Unknown matchType:** Treated as "ALL" for safety
3. **Expiry Dates:** All qualifications still checked for expiry
4. **Employee Must Satisfy ALL Groups:** Failing any one group blocks assignment

## Testing

### Test Input File

See: `input/test_qualification_groups.json`

This file demonstrates:
- ✅ Group with `matchType="ANY"` (screening method)
- ✅ Group with `matchType="ALL"` (custody authority)
- ✅ Backwards compatibility (REQ_BASIC uses simple array)
- ✅ Employees that pass (have valid combinations)
- ❌ Employees that fail (missing required qualifications)

### Expected Behavior

**REQ_SCREENING** (uses groups):
- Should assign: EMP_001, EMP_002, EMP_003
- Should NOT assign: EMP_004_FAILS (missing DETENTION-LIC), EMP_005_FAILS (missing screening method)

**REQ_BASIC** (uses simple array):
- Should assign any employee with BASIC-SECURITY-LIC

## Constraint Reporting

The C7 constraint now reports enhanced statistics:

```
[C7] License Validity Constraint (HARD)
     Employees: 5 (5 have licenses)
     Slots: 14 (14 require qualifications)
     Qualification Groups: 28 total (21 ALL, 7 ANY)
     Blocked Assignments: 28
```

## Implementation Details

### Normalization (slot_builder.py)

The `normalize_qualifications()` function:
1. Detects format (simple array vs groups)
2. Converts simple arrays to single group with `matchType="ALL"`
3. Validates and normalizes group structure
4. Returns unified group format

### Evaluation (C7_license_validity.py)

The `evaluate_qualification_groups()` function:
1. Iterates through all groups
2. For `matchType="ALL"`: checks employee has ALL qualifications
3. For `matchType="ANY"`: checks employee has AT LEAST ONE qualification
4. Returns true only if ALL groups satisfied
5. Checks expiry dates for all qualifications

## Edge Cases Handled

1. **Empty requiredQualifications:** No constraints applied
2. **Empty group qualifications:** Group skipped
3. **Invalid expiry dates:** Treated as expired
4. **Unknown matchType:** Treated as "ALL"
5. **Mixed format:** Not allowed (must be all simple or all groups)

## Future Enhancements

Possible future `matchType` values:
- `"AT_LEAST_N"`: Employee must have at least N qualifications from group
- `"EXACTLY_N"`: Employee must have exactly N qualifications from group
- `"NONE"`: Employee must NOT have any of these qualifications (exclusion)

## Support

For questions or issues:
1. Check test file: `input/test_qualification_groups.json`
2. Review constraint output in solver logs
3. Verify qualification codes match between requirements and employees
4. Check expiry dates are valid and in future
