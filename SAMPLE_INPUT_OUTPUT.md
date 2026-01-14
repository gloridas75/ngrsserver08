# Sample Input & Output JSON Files

## Example 1: Feasible Assignment (No Violations)

### INPUT: `test_assignment_validation.json`

```json
{
  "employee": {
    "employeeId": "00097227",
    "rankId": "SO",
    "productTypeId": "Guarding",
    "gender": "M",
    "ouId": "PB T1 A1",
    "scheme": "Scheme A",
    "rotationOffset": 2,
    "workPattern": ["D", "D", "D", "O", "O", "D", "D"],
    "normalHours": 184.8,
    "otHours": 35.2
  },
  "existingAssignments": [
    {
      "assignmentId": "DI-2601031507-71323393-2026-01-13-D-00097227",
      "demandId": "DI-2601031507-71323393",
      "requirementId": "230_1",
      "date": "2026-01-13",
      "slotId": "DI-2601031507-71323393-230_1-D-P1-2026-01-13-c0b135",
      "shiftCode": "D",
      "patternDay": 0,
      "startDateTime": "2026-01-13T07:00:00",
      "endDateTime": "2026-01-13T15:00:00",
      "employeeId": "00097227",
      "newRotationOffset": 0,
      "status": "ASSIGNED",
      "hours": {
        "gross": 8,
        "lunch": 1,
        "normal": 7,
        "ot": 0,
        "restDayPay": 0,
        "paid": 8
      }
    },
    {
      "assignmentId": "DI-2601031507-71323393-2026-01-14-D-00097227",
      "demandId": "DI-2601031507-71323393",
      "requirementId": "230_1",
      "date": "2026-01-14",
      "slotId": "DI-2601031507-71323393-230_1-D-P1-2026-01-14-c0b136",
      "shiftCode": "D",
      "patternDay": 1,
      "startDateTime": "2026-01-14T07:00:00",
      "endDateTime": "2026-01-14T15:00:00",
      "employeeId": "00097227",
      "newRotationOffset": 1,
      "status": "ASSIGNED",
      "hours": {
        "gross": 8,
        "lunch": 1,
        "normal": 7,
        "ot": 0,
        "restDayPay": 0,
        "paid": 8
      }
    }
  ],
  "candidateSlots": [
    {
      "slotId": "slot_unassigned_456",
      "demandItemId": "DI005",
      "requirementId": "REQ_R1",
      "startDateTime": "2026-01-16T07:00:00+08:00",
      "endDateTime": "2026-01-16T15:00:00+08:00",
      "shiftCode": "D"
    }
  ],
  "planningReference": {
    "startDate": "2026-01-01",
    "endDate": "2026-01-31",
    "ouName": "Security Division"
  },
  "constraintList": [
    {
      "constraintId": "C1",
      "enabled": true
    },
    {
      "constraintId": "C2",
      "enabled": true
    },
    {
      "constraintId": "C3",
      "enabled": true
    },
    {
      "constraintId": "C4",
      "enabled": true
    },
    {
      "constraintId": "C17",
      "enabled": true
    }
  ]
}
```

### OUTPUT: Success Response (No Violations)

```json
{
  "status": "success",
  "validationResults": [
    {
      "slotId": "slot_unassigned_456",
      "isFeasible": true,
      "violations": [],
      "recommendation": "feasible",
      "hours": {
        "gross": 8.0,
        "lunch": 1.0,
        "normal": 7.0,
        "ot": 0.0,
        "restDayPay": 0.0,
        "paid": 8.0
      }
    }
  ],
  "employeeId": "00097227",
  "timestamp": "2026-01-14T11:39:32.438520",
  "processingTimeMs": 1.31
}
```

**Interpretation:**
- ✅ `isFeasible: true` - Assignment is valid
- ✅ `violations: []` - No constraint violations detected
- ✅ `recommendation: "feasible"` - Safe to assign employee to this slot
- ✅ `hours` - Automatically calculated breakdown:
  - Gross: 8h (shift duration)
  - Lunch: 1h (deducted for shifts >6h)
  - Normal: 7h (gross - lunch, capped at 8h)
  - OT: 0h (no overtime for this shift)
  - Paid: 8h total
- ⚡ Processing time: 1.31ms (very fast!)

---

## Example 2: Infeasible Assignment (With Violations)

### INPUT: `test_assignment_validation_with_violation.json`

```json
{
  "employee": {
    "employeeId": "00034531",
    "rankId": "SO",
    "productTypeId": "AVSO",
    "gender": "F",
    "ouId": "PB T1 A1",
    "scheme": "Scheme P",
    "rotationOffset": 0,
    "workPattern": ["D", "D", "O", "D", "D", "O", "O"],
    "normalHours": 120.0,
    "otHours": 12.5
  },
  "existingAssignments": [],
  "candidateSlots": [
    {
      "slotId": "slot_long_shift",
      "demandItemId": "DI-2601031507-71323393",
      "requirementId": "230_1",
      "startDateTime": "2026-01-15T07:00:00+08:00",
      "endDateTime": "2026-01-15T19:00:00+08:00",
      "shiftCode": "D"
    }
  ],
  "constraintList": [
    {
      "constraintId": "C1",
      "enabled": true
    }
  ]
}
```

**Scenario:** Employee on Scheme P (9h daily cap) trying to work a 12-hour shift

### OUTPUT: Error Response (With Violations)

```json
{
  "status": "success",
  "validationResults": [
    {
      "slotId": "slot_long_shift",
      "isFeasible": false,
      "violations": [
        {
          "constraintId": "C1",
          "constraintName": "Daily Hours Cap",
          "violationType": "hard",
          "description": "Shift duration 11.0h exceeds daily cap of 9.0h for Scheme P",
          "context": {
            "shiftHours": 11.0,
            "dailyCap": 9.0,
            "scheme": "P",
            "date": "2026-01-15"
          }
        }
      ],
      "recommendation": "not_feasible",
      "hours": {
        "gross": 12.0,
        "lunch": 1.0,
        "normal": 8.0,
        "ot": 3.0,
        "restDayPay": 0.0,
        "paid": 12.0
      }
    }
  ],
  "employeeId": "00034531",
  "timestamp": "2026-01-14T11:39:40.315460",
  "processingTimeMs": 1.32
}
```

**Interpretation:**
- ❌ `isFeasible: false` - Assignment violates constraints
- ❌ `violations: [...]` - Detailed violation information
  - **Constraint:** C1 (Daily Hours Cap)
  - **Problem:** 11h working hours (12h gross - 1h lunch) exceeds 9h limit for Scheme P
  - **Context:** Provides numeric details for UI display
- ❌ `recommendation: "not_feasible"` - BLOCK this assignment
- ℹ️ `hours` - Shows the breakdown even for invalid assignments:
  - Gross: 12h (shift duration 07:00-19:00)
  - Lunch: 1h (deducted)
  - Normal: 8h (capped at 8h per day)
  - OT: 3h (12 - 1 lunch - 8 normal = 3h OT)
  - Paid: 12h total
- ⚡ Processing time: 1.32ms

---

## Example 3: Multiple Slots Validation

### INPUT: Multiple Candidate Slots

```json
{
  "employee": {
    "employeeId": "EMP005",
    "name": "Michael Chen",
    "rank": "SO",
    "gender": "M",
    "scheme": "A"
  },
  "existingAssignments": [],
  "candidateSlots": [
    {
      "slotId": "slot_good_1",
      "startDateTime": "2026-01-15T07:00:00+08:00",
      "endDateTime": "2026-01-15T15:00:00+08:00",
      "shiftType": "DAY"
    },
    {
      "slotId": "slot_good_2",
      "startDateTime": "2026-01-17T07:00:00+08:00",
      "endDateTime": "2026-01-17T15:00:00+08:00",
      "shiftType": "DAY"
    },
    {
      "slotId": "slot_too_long",
      "startDateTime": "2026-01-19T07:00:00+08:00",
      "endDateTime": "2026-01-19T22:00:00+08:00",
      "shiftType": "DAY"
    }
  ]
}
```

### OUTPUT: Mixed Results

```json
{
  "status": "success",
  "validationResults": [
    {
      "slotId": "slot_good_1",
      "isFeasible": true,
      "violations": [],
      "recommendation": "feasible",
      "hours": {
        "gross": 8.0,
        "lunch": 1.0,
        "normal": 7.0,
        "ot": 0.0,
        "restDayPay": 0.0,
        "paid": 8.0
      }
    },
    {
      "slotId": "slot_good_2",
      "isFeasible": true,
      "violations": [],
      "recommendation": "feasible",
      "hours": {
        "gross": 8.0,
        "lunch": 1.0,
        "normal": 7.0,
        "ot": 0.0,
        "restDayPay": 0.0,
        "paid": 8.0
      }
    },
    {
      "slotId": "slot_too_long",
      "isFeasible": false,
      "violations": [
        {
          "constraintId": "C1",
          "constraintName": "Daily Hours Cap",
          "violationType": "hard",
          "description": "Shift duration 14.0h exceeds daily cap of 14.0h for Scheme A",
          "context": {
            "shiftHours": 14.0,
            "dailyCap": 14.0,
            "scheme": "A",
            "date": "2026-01-19"
          }
        }
      ],
      "recommendation": "not_feasible",
      "hours": {
        "gross": 15.0,
        "lunch": 1.0,
        "normal": 8.0,
        "ot": 6.0,
        "restDayPay": 0.0,
        "paid": 15.0
      }
    }
  ],
  "employeeId": "EMP005",
  "timestamp": "2026-01-14T11:00:00.123456",
  "processingTimeMs": 3.45
}
```

**Interpretation:**
- ✅ Slot 1: OK (8h shift, 7h normal + 0h OT)
- ✅ Slot 2: OK (8h shift, 7h normal + 0h OT)
- ❌ Slot 3: FAIL (15h shift = 8h normal + 6h OT, exceeds 14h cap for Scheme A)
- 📊 Each slot includes its own hour breakdown
- 📊 Batch validation completed in 3.45ms for all 3 slots

---

## UI Display Examples

### Success Case (Green)
```
✅ Assignment Valid
Employee EMP001 can be assigned to slot_unassigned_456
No violations detected
```

### Error Case (Red)
```
❌ Assignment Blocked
Employee EMP002 cannot be assigned to slot_long_shift

Violation: Daily Hours Cap (C1)
• Shift duration 12.0h exceeds daily cap of 9.0h for Scheme P
• Date: 2026-01-15

This assignment violates MOM regulations and cannot proceed.
```

### Multiple Slots (List)
```
Validation Results for Michael Chen (EMP005):

✅ slot_good_1 - Can assign (8h shift on Jan 15)
✅ slot_good_2 - Can assign (8h shift on Jan 17)
❌ slot_too_long - Cannot assign
   Reason: 15h exceeds 14h daily limit (Scheme A)
```

---

## Field Descriptions

### Request Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `employee` | Object | Yes | Employee information |
| `employee.employeeId` | String | Yes | Unique employee ID |
| `employee.scheme` | String | Yes | Scheme type: A, B, or P |
| `existingAssignments` | Array | No | Current assignments (for context) |
| `candidateSlots` | Array | Yes | Slots to validate (1 or more) |
| `constraintList` | Array | No | Which constraints to check |

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `status` | String | "success" or "error" |
| `validationResults` | Array | One result per candidate slot |
| `validationResults[].slotId` | String | Slot identifier |
| `validationResults[].isFeasible` | Boolean | true = can assign, false = blocked |
| `validationResults[].violations` | Array | List of constraint violations (empty if feasible) |
| `validationResults[].hours` | Object | **NEW** Hour breakdown for the candidate slot |
| `validationResults[].hours.gross` | Float | Gross shift duration (end - start) |
| `validationResults[].hours.lunch` | Float | Lunch deduction (1h for shifts >6h) |
| `validationResults[].hours.normal` | Float | Normal working hours (capped at 8h) |
| `validationResults[].hours.ot` | Float | Overtime hours (beyond 8h) |
| `validationResults[].hours.paid` | Float | Total paid hours (gross hours) |
| `violations[].constraintId` | String | C1, C2, C3, C4, or C17 |
| `violations[].description` | String | Human-readable error message |
| `violations[].context` | Object | Numeric details (hours, limits, dates) |
| `processingTimeMs` | Number | Time taken to validate (typically 1-3ms) |

---

## Testing Commands

```bash
# Test feasible case
curl -X POST http://localhost:8080/validate/assignment \
  -H "Content-Type: application/json" \
  -d @test_assignment_validation.json

# Test violation case
curl -X POST http://localhost:8080/validate/assignment \
  -H "Content-Type: application/json" \
  -d @test_assignment_validation_with_violation.json

# Run comprehensive test suite
python test_validator_comprehensive.py
```

---

## Files Available

- ✅ `test_assignment_validation.json` - Feasible case (no violations)
- ✅ `test_assignment_validation_with_violation.json` - C1 violation example
- ✅ `test_assignment_validation_output.json` - Success output sample
- ✅ `test_validator_quick.py` - Quick test script
- ✅ `test_validator_comprehensive.py` - Full test suite
