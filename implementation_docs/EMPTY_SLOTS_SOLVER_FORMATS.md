# Empty Slots Solver - Input Format Options

## Overview

Three lightweight approaches to fill unassigned/empty slots **without** requiring the full `previousOutput` JSON (~500KB-1MB). These are optimized alternatives to the full Incremental Solver (v0.80).

---

## Option 1: Empty Slots + Locked Employee Context

**Use Case:** Fill unassigned slots with context about what employees have already worked.

**Pros:**
- ✅ Respects weekly hours already worked
- ✅ Considers consecutive days streak
- ✅ Accounts for rotation offsets
- ✅ Prevents constraint violations

**Cons:**
- ⚠️ Requires calculating locked context (weekly hours, streak, etc.)
- ⚠️ More complex input preparation

### Input Format

```json
{
  "schemaVersion": "0.96",
  "mode": "fillEmptySlotsWithContext",
  "planningReference": "DEC2025_FILL_v1",
  
  "emptySlots": [
    {
      "date": "2025-12-15",
      "shiftCode": "D",
      "requirementId": "52_1",
      "slotId": "SLOT-001",
      "reason": "UNASSIGNED",
      "demandId": "DI-2512060518-61035715",
      "startTime": "09:00:00",
      "endTime": "18:00:00",
      "hours": {
        "gross": 9,
        "lunch": 1,
        "normal": 8,
        "ot": 0
      }
    },
    {
      "date": "2025-12-16",
      "shiftCode": "N",
      "requirementId": "53_1",
      "slotId": "SLOT-002",
      "reason": "DEPARTED",
      "demandId": "DI-2512060518-61035716",
      "startTime": "22:00:00",
      "endTime": "07:00:00",
      "hours": {
        "gross": 9,
        "lunch": 1,
        "normal": 8,
        "ot": 0
      }
    }
  ],
  
  "lockedContext": {
    "cutoffDate": "2025-12-14",
    "solveFromDate": "2025-12-15",
    "solveToDate": "2025-12-31",
    
    "employees": {
      "00073354": {
        "weeklyHours": {
          "2025-W50": 32.0,
          "2025-W51": 12.0
        },
        "consecutiveDaysStreak": 3,
        "lastWorkDate": "2025-12-14",
        "rotationOffset": 3,
        "currentPatternDay": 2
      },
      "00158151": {
        "weeklyHours": {
          "2025-W50": 40.0,
          "2025-W51": 8.0
        },
        "consecutiveDaysStreak": 5,
        "lastWorkDate": "2025-12-13",
        "rotationOffset": 0,
        "currentPatternDay": 6
      }
    }
  },
  
  "employeePool": ["00073354", "00158151", "00027821"],
  
  "newJoiners": [
    {
      "employeeId": "NEW001",
      "firstName": "Sarah",
      "lastName": "Smith",
      "rankId": "SER",
      "productTypes": ["APO"],
      "workPattern": ["D", "D", "D", "D", "O", "D", "D"],
      "rotationOffset": 0,
      "contractedHours": 176.0,
      "availableFrom": "2025-12-15"
    }
  ],
  
  "requirements": [
    {
      "requirementId": "52_1",
      "productType": "APO",
      "rankId": "SER",
      "headcount": 10,
      "workPattern": ["D", "D", "D", "O", "O", "D", "D"]
    },
    {
      "requirementId": "53_1",
      "productType": "APO",
      "rankId": "SER",
      "headcount": 15,
      "workPattern": ["D", "D", "D", "D", "O", "D", "D"]
    }
  ],
  
  "solverConfig": {
    "timeLimitSeconds": 60
  }
}
```

### Field Descriptions

#### `emptySlots` (required)
Array of unassigned slots to fill.

**Fields:**
- `date` (required): Date of slot (YYYY-MM-DD)
- `shiftCode` (required): Shift code (D/N/E/O)
- `requirementId` (required): Requirement this slot belongs to
- `slotId` (optional): Unique slot identifier
- `reason` (optional): Why slot is empty ("UNASSIGNED", "DEPARTED", "LEAVE")
- `demandId` (optional): Demand item ID
- `startTime` (required): Shift start time (HH:MM:SS)
- `endTime` (required): Shift end time (HH:MM:SS)
- `hours` (required): Hour breakdown

#### `lockedContext` (required)
Context about what employees have already worked.

**Fields:**
- `cutoffDate`: Last date with locked assignments
- `solveFromDate`: First date to solve
- `solveToDate`: Last date in planning horizon
- `employees`: Map of employeeId → locked state
  - `weeklyHours`: Map of week → hours worked (e.g., "2025-W50": 32.0)
  - `consecutiveDaysStreak`: Days worked consecutively leading to cutoff
  - `lastWorkDate`: Most recent work date
  - `rotationOffset`: Current rotation offset
  - `currentPatternDay`: Current position in work pattern (0-6)

#### `employeePool` (required)
Array of existing employee IDs available for assignment.

#### `newJoiners` (optional)
New employees to add (full employee objects).

#### `requirements` (required)
Requirement definitions for pattern matching.

---

## Option 2: Empty Slots + Joiners Only

**Use Case:** Simply fill empty slots with new employees, ignore existing employee context.

**Pros:**
- ✅ Simplest format
- ✅ Minimal payload
- ✅ Easy to construct

**Cons:**
- ⚠️ No constraint tracking (may violate weekly hours, consecutive days)
- ⚠️ Best for scenarios where only new joiners will fill slots

### Input Format

```json
{
  "schemaVersion": "0.96",
  "mode": "fillEmptySlots",
  "planningReference": "DEC2025_JOINERS_v1",
  
  "emptySlots": [
    {
      "date": "2025-12-15",
      "shiftCode": "D",
      "requirementId": "52_1",
      "slotId": "SLOT-001",
      "startTime": "09:00:00",
      "endTime": "18:00:00",
      "hours": {
        "gross": 9,
        "lunch": 1,
        "normal": 8,
        "ot": 0
      }
    },
    {
      "date": "2025-12-16",
      "shiftCode": "N",
      "requirementId": "53_1",
      "slotId": "SLOT-002",
      "startTime": "22:00:00",
      "endTime": "07:00:00",
      "hours": {
        "gross": 9,
        "lunch": 1,
        "normal": 8,
        "ot": 0
      }
    }
  ],
  
  "newJoiners": [
    {
      "employeeId": "NEW001",
      "firstName": "Sarah",
      "lastName": "Smith",
      "rankId": "SER",
      "productTypes": ["APO"],
      "workPattern": ["D", "D", "D", "D", "O", "D", "D"],
      "rotationOffset": 0,
      "contractedHours": 176.0,
      "availableFrom": "2025-12-15"
    },
    {
      "employeeId": "NEW002",
      "firstName": "John",
      "lastName": "Doe",
      "rankId": "SER",
      "productTypes": ["APO"],
      "workPattern": ["D", "D", "D", "D", "O", "D", "D"],
      "rotationOffset": 0,
      "contractedHours": 176.0,
      "availableFrom": "2025-12-15"
    }
  ],
  
  "requirements": [
    {
      "requirementId": "52_1",
      "productType": "APO",
      "rankId": "SER",
      "headcount": 10,
      "workPattern": ["D", "D", "D", "O", "O", "D", "D"]
    },
    {
      "requirementId": "53_1",
      "productType": "APO",
      "rankId": "SER",
      "headcount": 15,
      "workPattern": ["D", "D", "D", "D", "O", "D", "D"]
    }
  ],
  
  "planningHorizon": {
    "startDate": "2025-12-01",
    "endDate": "2025-12-31",
    "lengthDays": 31
  },
  
  "solverConfig": {
    "timeLimitSeconds": 60
  }
}
```

### Field Descriptions

#### `emptySlots` (required)
Array of slots to fill (same structure as Option 1).

#### `newJoiners` (required)
New employees who will fill the slots.

#### `requirements` (required)
Requirement definitions for pattern validation.

#### `planningHorizon` (required)
Planning period metadata.

---

## Option 3: Empty Slots + Existing Employees + Joiners

**Use Case:** Fill slots with mix of existing and new employees, with availability tracking.

**Pros:**
- ✅ Balanced approach
- ✅ Tracks available hours/days per employee
- ✅ Can use both existing and new employees
- ✅ Prevents over-scheduling

**Cons:**
- ⚠️ Requires calculating available hours/days
- ⚠️ Medium complexity

### Input Format

```json
{
  "schemaVersion": "0.96",
  "mode": "fillEmptySlotsWithAvailability",
  "planningReference": "DEC2025_MIXED_v1",
  
  "emptySlots": [
    {
      "date": "2025-12-15",
      "shiftCode": "D",
      "requirementId": "52_1",
      "slotId": "SLOT-001",
      "startTime": "09:00:00",
      "endTime": "18:00:00",
      "hours": {
        "gross": 9,
        "lunch": 1,
        "normal": 8,
        "ot": 0
      }
    },
    {
      "date": "2025-12-20",
      "shiftCode": "D",
      "requirementId": "52_1",
      "slotId": "SLOT-003",
      "startTime": "09:00:00",
      "endTime": "18:00:00",
      "hours": {
        "gross": 9,
        "lunch": 1,
        "normal": 8,
        "ot": 0
      }
    }
  ],
  
  "existingEmployees": [
    {
      "employeeId": "00073354",
      "availableHours": {
        "weekly": 12.0,
        "monthly": 48.0
      },
      "availableDays": {
        "consecutive": 9,
        "total": 15
      },
      "currentState": {
        "consecutiveDaysWorked": 3,
        "lastWorkDate": "2025-12-14",
        "rotationOffset": 3,
        "patternDay": 2
      },
      "availability": [
        {"date": "2025-12-15", "available": true},
        {"date": "2025-12-16", "available": true},
        {"date": "2025-12-17", "available": false}
      ]
    },
    {
      "employeeId": "00158151",
      "availableHours": {
        "weekly": 36.0,
        "monthly": 144.0
      },
      "availableDays": {
        "consecutive": 7,
        "total": 18
      },
      "currentState": {
        "consecutiveDaysWorked": 5,
        "lastWorkDate": "2025-12-13",
        "rotationOffset": 0,
        "patternDay": 6
      },
      "availability": [
        {"date": "2025-12-15", "available": true},
        {"date": "2025-12-16", "available": true}
      ]
    }
  ],
  
  "newJoiners": [
    {
      "employeeId": "NEW001",
      "firstName": "Sarah",
      "lastName": "Smith",
      "rankId": "SER",
      "productTypes": ["APO"],
      "workPattern": ["D", "D", "D", "D", "O", "D", "D"],
      "rotationOffset": 0,
      "contractedHours": 176.0,
      "availableFrom": "2025-12-15"
    }
  ],
  
  "requirements": [
    {
      "requirementId": "52_1",
      "productType": "APO",
      "rankId": "SER",
      "headcount": 10,
      "workPattern": ["D", "D", "D", "O", "O", "D", "D"]
    },
    {
      "requirementId": "53_1",
      "productType": "APO",
      "rankId": "SER",
      "headcount": 15,
      "workPattern": ["D", "D", "D", "D", "O", "D", "D"]
    }
  ],
  
  "planningHorizon": {
    "startDate": "2025-12-01",
    "endDate": "2025-12-31",
    "lengthDays": 31
  },
  
  "solverConfig": {
    "timeLimitSeconds": 60
  }
}
```

### Field Descriptions

#### `existingEmployees` (required)
Existing employees with availability tracking.

**Fields:**
- `employeeId`: Employee identifier
- `availableHours`: Remaining hours capacity
  - `weekly`: Hours available this week (44 - already_worked)
  - `monthly`: Hours available this month (352 - already_worked)
- `availableDays`: Remaining days capacity
  - `consecutive`: More days can work consecutively (12 - streak)
  - `total`: Total days available in planning period
- `currentState`: Current rotation state
  - `consecutiveDaysWorked`: Days worked leading to today
  - `lastWorkDate`: Most recent work date
  - `rotationOffset`: Rotation offset
  - `patternDay`: Current day in work pattern (0-6)
- `availability`: Date-specific availability (optional)

---

## Comparison Matrix

| Feature | Option 1 | Option 2 | Option 3 |
|---------|----------|----------|----------|
| **Payload Size** | Medium | Minimal | Medium |
| **Constraint Tracking** | Full | None | Partial |
| **Weekly Hours** | ✅ Yes | ❌ No | ✅ Yes |
| **Consecutive Days** | ✅ Yes | ❌ No | ✅ Yes |
| **Rotation Offset** | ✅ Yes | ❌ No | ✅ Yes |
| **Existing Employees** | ✅ Yes | ❌ No | ✅ Yes |
| **New Joiners** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Input Complexity** | High | Low | Medium |
| **Best For** | Precise constraint compliance | Quick joiner-only fills | Balanced approach |

---

## Recommended API Endpoints

### Option 1: Fill Empty Slots with Context
```
POST /solve/fill-slots-with-context
```

### Option 2: Fill Empty Slots (Joiners Only)
```
POST /solve/fill-slots
```

### Option 3: Fill Empty Slots with Availability
```
POST /solve/fill-slots-mixed
```

---

## Proposed Implementation

### Pydantic Models (src/models.py)

```python
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

class EmptySlot(BaseModel):
    """Definition of an empty/unassigned slot to fill."""
    date: str = Field(..., description="Slot date (YYYY-MM-DD)")
    shiftCode: str = Field(..., description="Shift code (D/N/E/O)")
    requirementId: str = Field(..., description="Requirement ID")
    slotId: Optional[str] = Field(None, description="Unique slot ID")
    reason: Optional[str] = Field(None, description="Why empty (UNASSIGNED/DEPARTED/LEAVE)")
    demandId: Optional[str] = Field(None, description="Demand item ID")
    startTime: str = Field(..., description="Shift start time (HH:MM:SS)")
    endTime: str = Field(..., description="Shift end time (HH:MM:SS)")
    hours: Dict[str, float] = Field(..., description="Hour breakdown")


class LockedEmployeeContext(BaseModel):
    """Locked context for an existing employee."""
    weeklyHours: Dict[str, float] = Field(..., description="Week → hours worked")
    consecutiveDaysStreak: int = Field(0, description="Consecutive days worked")
    lastWorkDate: Optional[str] = Field(None, description="Last work date")
    rotationOffset: int = Field(0, description="Rotation offset")
    currentPatternDay: int = Field(0, description="Current pattern day (0-6)")


class LockedContext(BaseModel):
    """Locked assignment context."""
    cutoffDate: str = Field(..., description="Last locked date")
    solveFromDate: str = Field(..., description="First date to solve")
    solveToDate: str = Field(..., description="Last date to solve")
    employees: Dict[str, LockedEmployeeContext] = Field(
        default_factory=dict,
        description="Employee ID → locked context"
    )


class EmployeeAvailability(BaseModel):
    """Availability for a specific date."""
    date: str = Field(..., description="Date (YYYY-MM-DD)")
    available: bool = Field(..., description="Is employee available?")


class ExistingEmployeeWithAvailability(BaseModel):
    """Existing employee with availability tracking."""
    employeeId: str = Field(..., description="Employee ID")
    availableHours: Dict[str, float] = Field(
        ...,
        description="Remaining hours: weekly, monthly"
    )
    availableDays: Dict[str, int] = Field(
        ...,
        description="Remaining days: consecutive, total"
    )
    currentState: Dict[str, Any] = Field(
        ...,
        description="Current rotation state"
    )
    availability: Optional[List[EmployeeAvailability]] = Field(
        None,
        description="Date-specific availability"
    )


# Option 1: Fill Slots with Context
class FillSlotsWithContextRequest(BaseModel):
    """Fill empty slots with locked employee context."""
    schemaVersion: str = Field("0.96")
    mode: str = Field("fillEmptySlotsWithContext")
    planningReference: str = Field(..., description="Planning reference")
    emptySlots: List[EmptySlot] = Field(..., description="Slots to fill")
    lockedContext: LockedContext = Field(..., description="Locked employee context")
    employeePool: List[str] = Field(..., description="Existing employee IDs")
    newJoiners: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list,
        description="New employees"
    )
    requirements: List[Dict[str, Any]] = Field(..., description="Requirements")
    solverConfig: Optional[Dict[str, Any]] = Field(None)


# Option 2: Fill Slots (Joiners Only)
class FillSlotsRequest(BaseModel):
    """Fill empty slots with new joiners only."""
    schemaVersion: str = Field("0.96")
    mode: str = Field("fillEmptySlots")
    planningReference: str = Field(..., description="Planning reference")
    emptySlots: List[EmptySlot] = Field(..., description="Slots to fill")
    newJoiners: List[Dict[str, Any]] = Field(..., description="New employees")
    requirements: List[Dict[str, Any]] = Field(..., description="Requirements")
    planningHorizon: Dict[str, Any] = Field(..., description="Planning horizon")
    solverConfig: Optional[Dict[str, Any]] = Field(None)


# Option 3: Fill Slots with Availability
class FillSlotsWithAvailabilityRequest(BaseModel):
    """Fill empty slots with mixed employees (existing + new)."""
    schemaVersion: str = Field("0.96")
    mode: str = Field("fillEmptySlotsWithAvailability")
    planningReference: str = Field(..., description="Planning reference")
    emptySlots: List[EmptySlot] = Field(..., description="Slots to fill")
    existingEmployees: List[ExistingEmployeeWithAvailability] = Field(
        ...,
        description="Existing employees with availability"
    )
    newJoiners: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list,
        description="New employees"
    )
    requirements: List[Dict[str, Any]] = Field(..., description="Requirements")
    planningHorizon: Dict[str, Any] = Field(..., description="Planning horizon")
    solverConfig: Optional[Dict[str, Any]] = Field(None)
```

---

## Handling Partial Month Re-runs

### Use Case: Re-run for Part of Month (e.g., Dec 16-31 only)

Option 3 handles partial month scenarios by:
1. Including only slots for the date range you want to re-solve
2. Calculating employee state **as of the cutoff date**
3. Setting appropriate planning horizon

### Example: Re-run Dec 16-31 Only

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
    // ONLY include slots from Dec 16-31
    {"date": "2025-12-16", "shiftCode": "D", "requirementId": "52_1", ...},
    {"date": "2025-12-17", "shiftCode": "D", "requirementId": "52_1", ...},
    // ... more slots until Dec 31
  ],
  
  "existingEmployees": [
    {
      "employeeId": "00073354",
      
      // Calculate availability FOR THE REMAINING PERIOD (Dec 16-31)
      "availableHours": {
        "weekly": 12.0,     // Remaining hours in current week (W50)
        "monthly": 120.0    // Remaining hours for Dec 16-31 period
      },
      
      "availableDays": {
        "consecutive": 9,   // Can work 9 more consecutive days (12 - 3 already worked)
        "total": 16         // 16 days in Dec 16-31 period
      },
      
      // State AS OF Dec 15 (cutoff date)
      "currentState": {
        "consecutiveDaysWorked": 3,    // Worked 3 consecutive days up to Dec 15
        "lastWorkDate": "2025-12-14",  // Last worked on Dec 14
        "rotationOffset": 3,
        "patternDay": 2                // Currently at pattern day 2
      },
      
      // Optional: Specific availability for Dec 16-31
      "availability": [
        {"date": "2025-12-16", "available": true},
        {"date": "2025-12-17", "available": true},
        {"date": "2025-12-18", "available": false},  // On leave
        {"date": "2025-12-19", "available": false},  // On leave
        {"date": "2025-12-20", "available": true}
        // ... etc for Dec 16-31
      ]
    }
  ],
  
  "planningHorizon": {
    "startDate": "2025-12-16",  // Start from here
    "endDate": "2025-12-31",    // Until here
    "lengthDays": 16            // 16 days
  }
}
```

### Key Points for Partial Re-runs

1. **temporalWindow** (optional but recommended):
   - `cutoffDate`: Last date with locked assignments (Dec 15)
   - `solveFromDate`: First date to solve (Dec 16)
   - `solveToDate`: Last date to solve (Dec 31)

2. **emptySlots**: 
   - Include ONLY slots for Dec 16-31
   - Can include ALL slots (if doing full re-roster) or ONLY unassigned slots

3. **availableHours**:
   - Calculate based on what's already been worked in Dec 1-15
   - Weekly: Remaining hours in current week (44 - hours_worked_this_week)
   - Monthly: Remaining hours for the period (total_contracted - hours_worked_dec_1_15)

4. **availableDays**:
   - `consecutive`: 12 - consecutiveDaysWorked
   - `total`: Number of days in the solve period (16 days for Dec 16-31)

5. **currentState**:
   - Calculate AS OF the cutoff date (Dec 15)
   - `consecutiveDaysWorked`: Days worked leading up to cutoff
   - `lastWorkDate`: Most recent work date before solve period
   - `patternDay`: Where employee is in their work pattern

6. **planningHorizon**:
   - Set to the actual solve period (Dec 16-31)
   - Not the full month

---

## Calculation Example: Dec 16-31 Re-run

### Scenario
- Full month: Dec 1-31 (31 days)
- Locked: Dec 1-15 (15 days) ✅ Already rostered, don't touch
- Re-run: Dec 16-31 (16 days) 🔄 Re-solve these

### Employee State Calculation (as of Dec 15)

**Employee EMP001:**
- Already worked Dec 1-15:
  - Dec 1: 8h (D shift)
  - Dec 2: 8h (D shift)
  - Dec 3: 8h (D shift)
  - Dec 4: OFF
  - Dec 5: OFF
  - Dec 8: 8h (D shift)
  - Dec 9: 8h (D shift)
  - Total: 40 hours, 5 days worked, 3 consecutive (Dec 1-3)

**Calculate for Input:**
```json
{
  "employeeId": "EMP001",
  "availableHours": {
    "weekly": 4.0,      // Week W50 (Dec 8-14): 44 - 40 = 4h left this week
    "monthly": 136.0    // Month total: 176 - 40 = 136h available for Dec 16-31
  },
  "availableDays": {
    "consecutive": 9,   // 12 max - 3 worked = 9 more allowed
    "total": 16         // Dec 16-31 has 16 days
  },
  "currentState": {
    "consecutiveDaysWorked": 3,    // Worked Dec 1-3 consecutively
    "lastWorkDate": "2025-12-03",  // Last worked Dec 3
    "rotationOffset": 3,
    "patternDay": 5                // After 5 days into pattern
  }
}
```

---

## Use Cases for Partial Re-runs

### Use Case 1: Second Half of Month Only
**Scenario:** Lock first half (Dec 1-15), re-roster second half (Dec 16-31)

```json
{
  "temporalWindow": {
    "cutoffDate": "2025-12-15",
    "solveFromDate": "2025-12-16",
    "solveToDate": "2025-12-31"
  },
  "emptySlots": [/* All slots Dec 16-31 */],
  "existingEmployees": [/* State as of Dec 15 */]
}
```

### Use Case 2: Last Week Only
**Scenario:** Lock Dec 1-23, re-roster last week (Dec 24-31)

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

### Use Case 3: Fill Unassigned Slots Only (Any Date Range)
**Scenario:** Keep all existing assignments, fill only unassigned slots

```json
{
  "temporalWindow": {
    "cutoffDate": "2025-12-15",
    "solveFromDate": "2025-12-16",
    "solveToDate": "2025-12-31"
  },
  "emptySlots": [
    // ONLY unassigned slots (not all slots)
    {"date": "2025-12-18", "shiftCode": "D", "requirementId": "52_1", "reason": "UNASSIGNED"},
    {"date": "2025-12-22", "shiftCode": "N", "requirementId": "53_1", "reason": "UNASSIGNED"}
  ]
}
```

---

## My Recommendation

### **Use Option 3 (Fill Slots with Availability)**

**Why:**
1. ✅ **Best Balance** - Not too simple, not too complex
2. ✅ **Prevents Over-scheduling** - Tracks available hours/days
3. ✅ **Flexible** - Works with existing + new employees
4. ✅ **Moderate Payload** - Much smaller than full incremental (v0.80)
5. ✅ **Practical** - Most real-world scenarios need this level of detail
6. ✅ **Handles Partial Re-runs** - Supports any date range via temporalWindow

**When to Use Each:**
- **Option 1** - Maximum precision, full constraint compliance needed
- **Option 2** - Quick fill with new joiners only, no existing employee concerns
- **Option 3** - ⭐ **Recommended** - Most balanced, practical for 80% of cases

---

## Sample Use Case (Option 3)

**Scenario:** December roster has 15 unassigned slots. You have:
- 3 existing employees with remaining capacity
- 2 new joiners starting Dec 15

**Input:**
```json
{
  "mode": "fillEmptySlotsWithAvailability",
  "emptySlots": [/* 15 slots */],
  "existingEmployees": [
    {
      "employeeId": "EMP001",
      "availableHours": {"weekly": 12.0, "monthly": 48.0},
      "availableDays": {"consecutive": 7, "total": 12}
    },
    // ... 2 more
  ],
  "newJoiners": [/* 2 new employees */]
}
```

**Output:**
- Assignments for all 15 slots
- Respects available hours/days
- Uses both existing + new employees
- Optimal distribution

---

## Next Steps

1. **Choose Option** - I recommend **Option 3**
2. **Implement Models** - Add Pydantic models to `src/models.py`
3. **Create Solver Logic** - Add `src/fill_slots_solver.py`
4. **Add API Endpoint** - Add route to `src/api_server.py`
5. **Test** - Create test scenarios
6. **Deploy** - Update production

Would you like me to implement **Option 3** (recommended)?
