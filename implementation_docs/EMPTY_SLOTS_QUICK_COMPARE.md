# Empty Slots Solver - Quick Comparison

## Three Input Format Options

### Option 1: Empty Slots + Locked Context (Most Precise)
```json
{
  "mode": "fillEmptySlotsWithContext",
  "emptySlots": [...],
  "lockedContext": {
    "employees": {
      "EMP001": {
        "weeklyHours": {"2025-W50": 32.0},
        "consecutiveDaysStreak": 3,
        "rotationOffset": 3
      }
    }
  },
  "employeePool": ["EMP001", "EMP002"],
  "newJoiners": [...]
}
```
**Size:** ~5-10KB for 100 employees  
**Constraint Tracking:** ✅ Full (weekly hours, consecutive days, rotation)  
**Best For:** Maximum precision, compliance-critical scenarios

---

### Option 2: Empty Slots + Joiners Only (Simplest)
```json
{
  "mode": "fillEmptySlots",
  "emptySlots": [...],
  "newJoiners": [
    {
      "employeeId": "NEW001",
      "workPattern": ["D","D","D","D","O","D","D"],
      "availableFrom": "2025-12-15"
    }
  ]
}
```
**Size:** ~1-2KB  
**Constraint Tracking:** ❌ None  
**Best For:** Quick fills, new joiners only, no constraint concerns

---

### Option 3: Empty Slots + Availability (⭐ Recommended)
```json
{
  "mode": "fillEmptySlotsWithAvailability",
  "emptySlots": [...],
  "existingEmployees": [
    {
      "employeeId": "EMP001",
      "availableHours": {"weekly": 12.0, "monthly": 48.0},
      "availableDays": {"consecutive": 9, "total": 15},
      "currentState": {
        "consecutiveDaysWorked": 3,
        "rotationOffset": 3
      }
    }
  ],
  "newJoiners": [...]
}
```
**Size:** ~3-8KB for 100 employees  
**Constraint Tracking:** ✅ Partial (hours, days, rotation)  
**Best For:** ⭐ Most scenarios (80% of cases)

---

## Comparison Table

| Feature | Option 1 | Option 2 | Option 3 ⭐ |
|---------|----------|----------|------------|
| **Payload Size** | 5-10KB | 1-2KB | 3-8KB |
| **Input Complexity** | High | Low | Medium |
| **Weekly Hours Tracking** | ✅ | ❌ | ✅ |
| **Consecutive Days** | ✅ | ❌ | ✅ |
| **Rotation Offset** | ✅ | ❌ | ✅ |
| **Existing Employees** | ✅ | ❌ | ✅ |
| **New Joiners** | ✅ | ✅ | ✅ |
| **Prevents Over-scheduling** | ✅ | ❌ | ✅ |

---

## vs. Full Incremental Solver (v0.80)

| Metric | v0.80 | Option 3 | Savings |
|--------|-------|----------|---------|
| Payload Size | 500KB-1MB | 3-8KB | **99%** |
| Previous Output | Required | Not Required | ✅ |
| Calculation Needed | None | Medium | Availability calc |
| Use Case | Full re-roster | Fill empty slots | Different |

---

## Recommended Approach

### **Use Option 3** for most scenarios:

```json
{
  "schemaVersion": "0.96",
  "mode": "fillEmptySlotsWithAvailability",
  
  "emptySlots": [
    {
      "date": "2025-12-15",
      "shiftCode": "D",
      "requirementId": "52_1",
      "startTime": "09:00:00",
      "endTime": "18:00:00",
      "hours": {"gross": 9, "lunch": 1, "normal": 8, "ot": 0}
    }
  ],
  
  "existingEmployees": [
    {
      "employeeId": "EMP001",
      "availableHours": {"weekly": 12.0, "monthly": 48.0},
      "availableDays": {"consecutive": 9, "total": 15},
      "currentState": {
        "consecutiveDaysWorked": 3,
        "lastWorkDate": "2025-12-14",
        "rotationOffset": 3,
        "patternDay": 2
      }
    }
  ],
  
  "newJoiners": [
    {
      "employeeId": "NEW001",
      "workPattern": ["D","D","D","D","O","D","D"],
      "availableFrom": "2025-12-15"
    }
  ],
  
  "requirements": [...],
  "planningHorizon": {
    "startDate": "2025-12-01",
    "endDate": "2025-12-31"
  }
}
```

---

## API Endpoints (Proposed)

```
POST /solve/fill-slots-with-context     # Option 1
POST /solve/fill-slots                  # Option 2
POST /solve/fill-slots-mixed            # Option 3 ⭐
```

---

## Full Documentation

See: `EMPTY_SLOTS_SOLVER_FORMATS.md`
