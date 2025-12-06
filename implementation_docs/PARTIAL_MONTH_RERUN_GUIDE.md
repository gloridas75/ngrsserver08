# Partial Month Re-runs Guide (Option 3)

## Overview

This guide explains how to use **Option 3 (Fill Slots with Availability)** to re-run the solver for **part of a month** while keeping existing assignments intact.

---

## Concept: Temporal Window

A **temporal window** defines:
- **cutoffDate**: Last date with locked assignments (don't touch)
- **solveFromDate**: First date to re-solve
- **solveToDate**: Last date to re-solve

```
December 2025
│
├────── Dec 1-15 ──────┤────── Dec 16-31 ──────┤
│                      │                        │
│   LOCKED             │   RE-SOLVE             │
│   (keep as-is)       │   (generate new)       │
│                      │                        │
│                 cutoffDate              solveToDate
│                 (Dec 15)                (Dec 31)
│                      └─ solveFromDate (Dec 16)
```

---

## Step-by-Step: Re-run Dec 16-31

### Step 1: Identify What's Locked

**Locked:** Dec 1-15 (already rostered, committed)  
**Re-solve:** Dec 16-31 (generate new assignments)

### Step 2: Extract Slots for Dec 16-31

Two approaches:

**Approach A: All Slots** (Full Re-roster)
- Extract ALL demand slots for Dec 16-31
- Solver will assign all from scratch
- Use when: Complete redo needed

**Approach B: Unassigned Only** (Fill Gaps)
- Extract only UNASSIGNED slots from Dec 16-31
- Keep existing assignments intact
- Use when: Just filling gaps

### Step 3: Calculate Employee State (as of Dec 15)

For each employee, calculate:

#### 3.1 Hours Already Worked
```python
# Example for Employee EMP001
worked_dec_1_15 = [
    {"date": "2025-12-01", "hours": 8},
    {"date": "2025-12-02", "hours": 8},
    {"date": "2025-12-03", "hours": 8},
    {"date": "2025-12-08", "hours": 8},
    {"date": "2025-12-09", "hours": 8}
]
total_hours = 40

# Current week (W50: Dec 8-14)
week_hours = 16  # Worked Dec 8, 9

# Calculate available
available_weekly = 44 - week_hours  # 28h left this week
available_monthly = 176 - total_hours  # 136h left for Dec 16-31
```

#### 3.2 Consecutive Days Streak
```python
# Find consecutive days leading to cutoff
consecutive_days = 0
check_date = "2025-12-15"

# Walk backwards from cutoff
if worked_on("2025-12-15"): consecutive_days += 1
if worked_on("2025-12-14"): consecutive_days += 1
else: break  # Streak broken

# For EMP001: Worked Dec 1-3, then OFF Dec 4-5
# Streak = 0 (no work immediately before cutoff)
```

#### 3.3 Last Work Date
```python
last_work_date = max([d["date"] for d in worked_dec_1_15])
# For EMP001: "2025-12-09"
```

#### 3.4 Current Pattern Day
```python
# Employee has 7-day pattern: [D,D,D,D,O,D,D]
# Started with offset 3

# Days since start of month
days_since_start = (cutoff_date - month_start).days  # Dec 15 - Dec 1 = 14

# Calculate pattern day
pattern_day = (days_since_start + rotation_offset) % 7
# = (14 + 3) % 7 = 17 % 7 = 3

# Employee is at pattern day 3 as of Dec 15
```

### Step 4: Construct Input JSON

```json
{
  "schemaVersion": "0.96",
  "mode": "fillEmptySlotsWithAvailability",
  "planningReference": "DEC2025_PARTIAL_16_31",
  
  "temporalWindow": {
    "cutoffDate": "2025-12-15",
    "solveFromDate": "2025-12-16",
    "solveToDate": "2025-12-31"
  },
  
  "emptySlots": [
    // Only slots from Dec 16-31
    {
      "date": "2025-12-16",
      "shiftCode": "D",
      "requirementId": "52_1",
      "slotId": "SLOT-DEC16-001",
      "startTime": "09:00:00",
      "endTime": "18:00:00",
      "hours": {"gross": 9, "lunch": 1, "normal": 8, "ot": 0}
    }
    // ... more slots for Dec 16-31
  ],
  
  "existingEmployees": [
    {
      "employeeId": "EMP001",
      "availableHours": {
        "weekly": 28.0,    // 44 - 16 worked in W50
        "monthly": 136.0   // 176 - 40 worked Dec 1-15
      },
      "availableDays": {
        "consecutive": 12,  // Max 12, streak is 0
        "total": 16         // 16 days in Dec 16-31
      },
      "currentState": {
        "consecutiveDaysWorked": 0,
        "lastWorkDate": "2025-12-09",
        "rotationOffset": 3,
        "patternDay": 3
      }
    }
  ],
  
  "newJoiners": [],  // Optional
  
  "requirements": [
    {
      "requirementId": "52_1",
      "productType": "APO",
      "rankId": "SER",
      "headcount": 10,
      "workPattern": ["D", "D", "D", "O", "O", "D", "D"]
    }
  ],
  
  "planningHorizon": {
    "startDate": "2025-12-16",
    "endDate": "2025-12-31",
    "lengthDays": 16
  }
}
```

---

## Calculation Helpers

### Python Script: Calculate Employee State

```python
from datetime import datetime, timedelta

def calculate_employee_state(employee_id, assignments_dec_1_15, cutoff_date):
    """
    Calculate employee state as of cutoff date.
    
    Args:
        employee_id: Employee ID
        assignments_dec_1_15: List of assignments from Dec 1-15
        cutoff_date: Cutoff date (e.g., "2025-12-15")
    
    Returns:
        Dict with employee state
    """
    # Filter assignments for this employee
    emp_assignments = [a for a in assignments_dec_1_15 if a['employeeId'] == employee_id]
    
    # Calculate total hours worked
    total_hours = sum(a['hours']['normal'] for a in emp_assignments)
    
    # Calculate current week hours
    cutoff = datetime.strptime(cutoff_date, "%Y-%m-%d")
    week_start = cutoff - timedelta(days=cutoff.weekday())
    week_hours = sum(
        a['hours']['normal'] for a in emp_assignments
        if datetime.strptime(a['date'], "%Y-%m-%d") >= week_start
    )
    
    # Calculate consecutive days streak
    consecutive_days = 0
    check_date = cutoff
    worked_dates = sorted([datetime.strptime(a['date'], "%Y-%m-%d") for a in emp_assignments])
    
    while check_date in worked_dates:
        consecutive_days += 1
        check_date -= timedelta(days=1)
    
    # Last work date
    last_work_date = max(worked_dates).strftime("%Y-%m-%d") if worked_dates else None
    
    # Available hours
    available_weekly = 44.0 - week_hours
    available_monthly = 176.0 - total_hours
    
    # Available consecutive days
    available_consecutive = 12 - consecutive_days
    
    return {
        "employeeId": employee_id,
        "availableHours": {
            "weekly": available_weekly,
            "monthly": available_monthly
        },
        "availableDays": {
            "consecutive": available_consecutive,
            "total": 16  # Days in solve period
        },
        "currentState": {
            "consecutiveDaysWorked": consecutive_days,
            "lastWorkDate": last_work_date,
            "rotationOffset": 3,  # From employee data
            "patternDay": calculate_pattern_day(cutoff_date, rotation_offset=3)
        }
    }

def calculate_pattern_day(date_str, month_start="2025-12-01", rotation_offset=0):
    """Calculate current pattern day."""
    date = datetime.strptime(date_str, "%Y-%m-%d")
    start = datetime.strptime(month_start, "%Y-%m-%d")
    days_since_start = (date - start).days
    return (days_since_start + rotation_offset) % 7
```

---

## Common Scenarios

### Scenario 1: Lock First Half, Re-solve Second Half

**Goal:** Keep Dec 1-15, redo Dec 16-31

```json
{
  "temporalWindow": {
    "cutoffDate": "2025-12-15",
    "solveFromDate": "2025-12-16",
    "solveToDate": "2025-12-31"
  },
  "emptySlots": [/* All slots Dec 16-31 */],
  "planningHorizon": {
    "startDate": "2025-12-16",
    "endDate": "2025-12-31",
    "lengthDays": 16
  }
}
```

### Scenario 2: Re-solve Last Week Only

**Goal:** Keep Dec 1-23, redo Dec 24-31

```json
{
  "temporalWindow": {
    "cutoffDate": "2025-12-23",
    "solveFromDate": "2025-12-24",
    "solveToDate": "2025-12-31"
  },
  "emptySlots": [/* All slots Dec 24-31 */],
  "planningHorizon": {
    "startDate": "2025-12-24",
    "endDate": "2025-12-31",
    "lengthDays": 8
  }
}
```

### Scenario 3: Fill Unassigned Slots in Second Half

**Goal:** Keep all existing assignments, fill only unassigned slots Dec 16-31

```json
{
  "temporalWindow": {
    "cutoffDate": "2025-12-15",
    "solveFromDate": "2025-12-16",
    "solveToDate": "2025-12-31"
  },
  "emptySlots": [
    // ONLY unassigned slots
    {"date": "2025-12-18", "shiftCode": "D", "requirementId": "52_1", "reason": "UNASSIGNED"},
    {"date": "2025-12-22", "shiftCode": "N", "requirementId": "53_1", "reason": "UNASSIGNED"}
  ]
}
```

### Scenario 4: Add New Joiner, Re-solve From Join Date

**Goal:** New employee joins Dec 20, re-solve Dec 20-31 only

```json
{
  "temporalWindow": {
    "cutoffDate": "2025-12-19",
    "solveFromDate": "2025-12-20",
    "solveToDate": "2025-12-31"
  },
  "emptySlots": [/* Unassigned slots Dec 20-31 */],
  "existingEmployees": [/* State as of Dec 19 */],
  "newJoiners": [
    {
      "employeeId": "NEW001",
      "availableFrom": "2025-12-20"
    }
  ]
}
```

---

## Data Extraction from Previous Output

### Extract Slots for Re-run Period

```python
def extract_slots_for_period(previous_output, start_date, end_date, unassigned_only=False):
    """
    Extract slots from previous output for a specific period.
    
    Args:
        previous_output: Full previous solver output
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        unassigned_only: If True, only extract unassigned slots
    
    Returns:
        List of empty slots
    """
    assignments = previous_output.get('assignments', [])
    empty_slots = []
    
    for assignment in assignments:
        date = assignment['date']
        
        # Check if in period
        if not (start_date <= date <= end_date):
            continue
        
        # Check if should include
        if unassigned_only and assignment['status'] != 'UNASSIGNED':
            continue
        
        # Create empty slot
        empty_slot = {
            "date": date,
            "shiftCode": assignment['shiftCode'],
            "requirementId": assignment['requirementId'],
            "slotId": assignment.get('slotId'),
            "startTime": assignment['startDateTime'].split('T')[1],
            "endTime": assignment['endDateTime'].split('T')[1],
            "hours": assignment['hours']
        }
        
        if assignment['status'] == 'UNASSIGNED':
            empty_slot['reason'] = 'UNASSIGNED'
        
        empty_slots.append(empty_slot)
    
    return empty_slots
```

### Extract Employee State

```python
def extract_employee_states(previous_output, cutoff_date, solve_to_date):
    """
    Extract employee states from previous output.
    
    Args:
        previous_output: Full previous solver output
        cutoff_date: Cutoff date (YYYY-MM-DD)
        solve_to_date: End of solve period (YYYY-MM-DD)
    
    Returns:
        List of existing employees with availability
    """
    from datetime import datetime, timedelta
    
    assignments = previous_output.get('assignments', [])
    employees = {}
    
    # Get unique employee IDs
    emp_ids = set(a['employeeId'] for a in assignments if a['status'] == 'ASSIGNED')
    
    for emp_id in emp_ids:
        # Get assignments before cutoff
        emp_assignments = [
            a for a in assignments
            if a['employeeId'] == emp_id
            and a['status'] == 'ASSIGNED'
            and a['date'] <= cutoff_date
        ]
        
        # Calculate state
        state = calculate_employee_state(emp_id, emp_assignments, cutoff_date)
        
        # Calculate days in solve period
        cutoff = datetime.strptime(cutoff_date, "%Y-%m-%d")
        solve_to = datetime.strptime(solve_to_date, "%Y-%m-%d")
        days_in_period = (solve_to - cutoff).days
        
        state['availableDays']['total'] = days_in_period
        
        employees[emp_id] = state
    
    return list(employees.values())
```

---

## Complete Example

### Input Data
- **Previous roster:** Dec 1-31 (completed)
- **Goal:** Re-solve Dec 16-31 only
- **Reason:** New employee joins Dec 16

### Process

1. **Load previous output**
   ```python
   with open('output/dec_2025_v1.json') as f:
       previous = json.load(f)
   ```

2. **Extract slots for Dec 16-31**
   ```python
   empty_slots = extract_slots_for_period(
       previous, 
       "2025-12-16", 
       "2025-12-31",
       unassigned_only=True  # Only unassigned
   )
   ```

3. **Calculate employee states as of Dec 15**
   ```python
   existing_employees = extract_employee_states(
       previous,
       "2025-12-15",
       "2025-12-31"
   )
   ```

4. **Construct request**
   ```python
   request = {
       "schemaVersion": "0.96",
       "mode": "fillEmptySlotsWithAvailability",
       "temporalWindow": {
           "cutoffDate": "2025-12-15",
           "solveFromDate": "2025-12-16",
           "solveToDate": "2025-12-31"
       },
       "emptySlots": empty_slots,
       "existingEmployees": existing_employees,
       "newJoiners": [new_employee_data],
       "requirements": previous['requirements'],
       "planningHorizon": {
           "startDate": "2025-12-16",
           "endDate": "2025-12-31",
           "lengthDays": 16
       }
   }
   ```

5. **Submit to API**
   ```python
   response = requests.post(
       "https://ngrssolver08.comcentricapps.com/solve/fill-slots-mixed",
       json=request
   )
   ```

---

## Key Benefits

✅ **No Full Previous Output** - Don't need 500KB-1MB JSON  
✅ **Flexible Date Ranges** - Any period (week, half-month, custom)  
✅ **Constraint-Aware** - Respects hours, consecutive days, rotation  
✅ **Lightweight** - 3-8KB payload vs. 500KB+  
✅ **Partial Re-roster** - Keep locked, solve only what's needed

---

## Summary

Option 3 handles partial month re-runs by:

1. **temporalWindow** - Define what to lock vs. solve
2. **emptySlots** - Include only slots for the solve period
3. **existingEmployees** - Calculate state as of cutoff date
4. **planningHorizon** - Set to the solve period (not full month)

This approach gives you **full flexibility** to re-run any date range while keeping the rest locked!
