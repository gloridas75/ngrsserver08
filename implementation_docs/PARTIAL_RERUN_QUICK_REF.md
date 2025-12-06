# Quick Guide: Partial Month Re-runs (Option 3)

## How It Works

### Define Temporal Window
```json
{
  "temporalWindow": {
    "cutoffDate": "2025-12-15",      // Lock everything before this
    "solveFromDate": "2025-12-16",   // Start solving from here
    "solveToDate": "2025-12-31"      // Until here
  }
}
```

### Visual Timeline
```
December 2025
│
├────── Dec 1-15 ──────┤────── Dec 16-31 ──────┤
│                      │                        │
│   LOCKED ✅          │   RE-SOLVE 🔄         │
│   Keep as-is         │   Generate new         │
│                      │                        │
│                 cutoffDate              solveToDate
│                 (Dec 15)                (Dec 31)
```

---

## Input Structure

```json
{
  "mode": "fillEmptySlotsWithAvailability",
  
  "temporalWindow": {
    "cutoffDate": "2025-12-15",
    "solveFromDate": "2025-12-16",
    "solveToDate": "2025-12-31"
  },
  
  "emptySlots": [
    // ONLY slots from Dec 16-31
    {"date": "2025-12-16", "shiftCode": "D", ...},
    {"date": "2025-12-17", "shiftCode": "D", ...}
  ],
  
  "existingEmployees": [
    {
      "employeeId": "EMP001",
      "availableHours": {
        "weekly": 28.0,     // 44 - already_worked_this_week
        "monthly": 136.0    // 176 - already_worked_dec_1_15
      },
      "availableDays": {
        "consecutive": 9,   // 12 - consecutive_days_worked
        "total": 16         // Days in Dec 16-31
      },
      "currentState": {
        "consecutiveDaysWorked": 3,
        "lastWorkDate": "2025-12-14",
        "rotationOffset": 3,
        "patternDay": 2
      }
    }
  ],
  
  "planningHorizon": {
    "startDate": "2025-12-16",  // Solve period start
    "endDate": "2025-12-31",    // Solve period end
    "lengthDays": 16
  }
}
```

---

## Key Calculations

### 1. Available Hours
```python
# Current week
available_weekly = 44 - hours_worked_this_week

# For solve period
available_monthly = contracted_hours - hours_worked_before_cutoff
```

### 2. Available Days
```python
# Consecutive
available_consecutive = 12 - consecutive_days_worked_up_to_cutoff

# Total
available_total = days_in_solve_period  # e.g., 16 for Dec 16-31
```

### 3. Pattern Day
```python
days_since_month_start = (cutoff_date - month_start).days
pattern_day = (days_since_month_start + rotation_offset) % 7
```

---

## Common Scenarios

### Scenario 1: Second Half Only
```json
{
  "temporalWindow": {
    "cutoffDate": "2025-12-15",
    "solveFromDate": "2025-12-16",
    "solveToDate": "2025-12-31"
  }
}
```

### Scenario 2: Last Week Only
```json
{
  "temporalWindow": {
    "cutoffDate": "2025-12-23",
    "solveFromDate": "2025-12-24",
    "solveToDate": "2025-12-31"
  }
}
```

### Scenario 3: Custom Range
```json
{
  "temporalWindow": {
    "cutoffDate": "2025-12-10",
    "solveFromDate": "2025-12-11",
    "solveToDate": "2025-12-20"
  }
}
```

---

## What Gets Locked vs. Re-solved

| Date Range | Status | What Happens |
|------------|--------|--------------|
| Before cutoffDate | 🔒 **LOCKED** | Keep existing assignments |
| cutoffDate | 🔒 **LOCKED** | Included in locked |
| solveFromDate to solveToDate | 🔄 **RE-SOLVE** | Generate new assignments |
| After solveToDate | ❌ **IGNORED** | Not included in solve |

---

## Data Extraction

### From Previous Output

```python
# 1. Extract slots for period
empty_slots = [
    a for a in previous_output['assignments']
    if solve_from <= a['date'] <= solve_to
    and a['status'] == 'UNASSIGNED'  # Optional filter
]

# 2. Calculate employee state as of cutoff
for employee in employees:
    worked_before_cutoff = [
        a for a in previous_output['assignments']
        if a['employeeId'] == employee['id']
        and a['date'] <= cutoff_date
    ]
    
    total_hours = sum(a['hours']['normal'] for a in worked_before_cutoff)
    available_hours = contracted_hours - total_hours
```

---

## Benefits

✅ **Flexible Periods** - Any date range (week, half, custom)  
✅ **Lightweight** - 3-8KB vs. 500KB+ full output  
✅ **Constraint-Aware** - Respects hours, consecutive days  
✅ **Surgical Re-roster** - Touch only what needs changing  
✅ **No Full Output** - Don't need entire previous roster

---

## API Endpoint (Proposed)

```
POST /solve/fill-slots-mixed
```

---

## Full Documentation

📖 **Detailed Guide:** `PARTIAL_MONTH_RERUN_GUIDE.md`  
📖 **Format Options:** `EMPTY_SLOTS_SOLVER_FORMATS.md`  
📖 **Quick Compare:** `EMPTY_SLOTS_QUICK_COMPARE.md`
