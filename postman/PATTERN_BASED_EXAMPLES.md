# Pattern-Based Scheduling Examples

This document provides ready-to-use examples for testing pattern-based scheduling with different optimization modes.

## Table of Contents
- [Example 1: balanceWorkload with D-D-N-N-O-O Pattern](#example-1-balanceworkload-with-d-d-n-n-o-o-pattern)
- [Example 2: minimizeEmployeeCount (Simple Coverage)](#example-2-minimizeemployeecount-simple-coverage)
- [Example 3: Testing Different Headcounts](#example-3-testing-different-headcounts)
- [Expected Results](#expected-results)

---

## Example 1: balanceWorkload with D-D-N-N-O-O Pattern

**Use Case:** Rotation-based scheduling with 6-day work pattern (2 days, 2 nights, 2 off)

**Configuration:**
- `optimizationMode`: "balanceWorkload"
- `fixedRotationOffset`: true
- Employees pre-distributed across offsets 0-5
- Pattern: D-D-N-N-O-O

**Request Body (POST /solve/async):**

```json
{
  "input_json": {
    "schemaVersion": "0.43",
    "planningHorizon": {
      "startDate": "2025-01-01",
      "endDate": "2025-01-31"
    },
    "publicHolidays": ["2025-01-01"],
    
    "optimizationMode": "balanceWorkload",
    "fixedRotationOffset": true,
    
    "shifts": [
      {
        "code": "D",
        "name": "Day Shift",
        "startTime": "08:00",
        "endTime": "20:00",
        "grossHours": 12.0,
        "lunchBreak": 1.0
      },
      {
        "code": "N",
        "name": "Night Shift",
        "startTime": "20:00",
        "endTime": "08:00",
        "grossHours": 12.0,
        "lunchBreak": 1.0
      }
    ],
    
    "employees": [
      {
        "employeeId": "E001",
        "name": "Alice Wong",
        "employeeType": "APO",
        "rank": "APO",
        "scheme": "A",
        "gender": "F",
        "availableShifts": ["D", "N"],
        "productTypes": ["APO"],
        "rotationOffset": 0
      },
      {
        "employeeId": "E002",
        "name": "Bob Tan",
        "employeeType": "APO",
        "rank": "APO",
        "scheme": "A",
        "gender": "M",
        "availableShifts": ["D", "N"],
        "productTypes": ["APO"],
        "rotationOffset": 1
      },
      {
        "employeeId": "E003",
        "name": "Charlie Lee",
        "employeeType": "APO",
        "rank": "APO",
        "scheme": "A",
        "gender": "M",
        "availableShifts": ["D", "N"],
        "productTypes": ["APO"],
        "rotationOffset": 2
      },
      {
        "employeeId": "E004",
        "name": "Diana Chen",
        "employeeType": "APO",
        "rank": "APO",
        "scheme": "A",
        "gender": "F",
        "availableShifts": ["D", "N"],
        "productTypes": ["APO"],
        "rotationOffset": 3
      },
      {
        "employeeId": "E005",
        "name": "Edward Lim",
        "employeeType": "APO",
        "rank": "APO",
        "scheme": "A",
        "gender": "M",
        "availableShifts": ["D", "N"],
        "productTypes": ["APO"],
        "rotationOffset": 4
      },
      {
        "employeeId": "E006",
        "name": "Fiona Ng",
        "employeeType": "APO",
        "rank": "APO",
        "scheme": "A",
        "gender": "F",
        "availableShifts": ["D", "N"],
        "productTypes": ["APO"],
        "rotationOffset": 5
      }
    ],
    
    "demandItems": [
      {
        "demandId": "D_PATROL_APO",
        "demandType": "APO",
        "location": "Terminal 1",
        "shifts": [
          {
            "shiftCode": "D",
            "headcount": 1,
            "minHeadcount": 1,
            "rotationSequence": ["D", "D", "N", "N", "O", "O"],
            "coverageAnchor": "2025-01-01",
            "whitelist": {
              "productTypes": ["APO"],
              "ranks": ["APO"],
              "schemes": ["A"]
            }
          }
        ]
      }
    ],
    
    "constraintList": [
      {
        "id": "apgdMaxWeeklyNormalHours",
        "type": "HARD",
        "params": {
          "maxNormalHours": 44.0
        }
      },
      {
        "id": "apgdMaxMonthlyOTHours",
        "type": "HARD",
        "params": {
          "maxOTHours": 72.0
        }
      },
      {
        "id": "apgdMaxConsecutiveWorkDays",
        "type": "HARD",
        "params": {
          "maxDays": 12
        }
      },
      {
        "id": "apgdMinOffDaysPerWeek",
        "type": "HARD",
        "params": {
          "minOffDays": 1
        }
      }
    ],
    
    "solverConfig": {
      "timeLimitSeconds": 300
    }
  }
}
```

**Expected Results:**
- **Status:** OPTIMAL
- **Employees Used:** 3 (50% utilization for headcount=1)
- **Shifts per Employee:** 20-21 shifts per month
- **Coverage:** 100% (all slots filled)
- **Efficiency:** 100.0-100.2%
- **Solve Time:** 10-30 seconds

---

## Example 2: minimizeEmployeeCount (Simple Coverage)

**Use Case:** Simple shift coverage without rotation patterns (no continuous adherence)

**Configuration:**
- `optimizationMode`: "minimizeEmployeeCount"
- `fixedRotationOffset`: false (not needed)
- No rotation patterns defined
- Simple day/night coverage

**Request Body (POST /solve/async):**

```json
{
  "input_json": {
    "schemaVersion": "0.43",
    "planningHorizon": {
      "startDate": "2025-01-01",
      "endDate": "2025-01-07"
    },
    
    "optimizationMode": "minimizeEmployeeCount",
    "fixedRotationOffset": false,
    
    "shifts": [
      {
        "code": "D",
        "name": "Day Shift",
        "startTime": "08:00",
        "endTime": "20:00",
        "grossHours": 12.0,
        "lunchBreak": 1.0
      },
      {
        "code": "N",
        "name": "Night Shift",
        "startTime": "20:00",
        "endTime": "08:00",
        "grossHours": 12.0,
        "lunchBreak": 1.0
      }
    ],
    
    "employees": [
      {
        "employeeId": "E001",
        "name": "Alice Wong",
        "employeeType": "APO",
        "rank": "APO",
        "scheme": "A",
        "gender": "F",
        "availableShifts": ["D", "N"],
        "productTypes": ["APO"]
      },
      {
        "employeeId": "E002",
        "name": "Bob Tan",
        "employeeType": "APO",
        "rank": "APO",
        "scheme": "A",
        "gender": "M",
        "availableShifts": ["D", "N"],
        "productTypes": ["APO"]
      },
      {
        "employeeId": "E003",
        "name": "Charlie Lee",
        "employeeType": "APO",
        "rank": "APO",
        "scheme": "A",
        "gender": "M",
        "availableShifts": ["D", "N"],
        "productTypes": ["APO"]
      }
    ],
    
    "demandItems": [
      {
        "demandId": "D_PATROL_APO",
        "demandType": "APO",
        "location": "Terminal 1",
        "shifts": [
          {
            "shiftCode": "D",
            "date": "2025-01-01",
            "headcount": 1,
            "minHeadcount": 1,
            "whitelist": {
              "productTypes": ["APO"],
              "ranks": ["APO"],
              "schemes": ["A"]
            }
          },
          {
            "shiftCode": "N",
            "date": "2025-01-01",
            "headcount": 1,
            "minHeadcount": 1,
            "whitelist": {
              "productTypes": ["APO"],
              "ranks": ["APO"],
              "schemes": ["A"]
            }
          },
          {
            "shiftCode": "D",
            "date": "2025-01-02",
            "headcount": 1,
            "minHeadcount": 1,
            "whitelist": {
              "productTypes": ["APO"],
              "ranks": ["APO"],
              "schemes": ["A"]
            }
          },
          {
            "shiftCode": "N",
            "date": "2025-01-02",
            "headcount": 1,
            "minHeadcount": 1,
            "whitelist": {
              "productTypes": ["APO"],
              "ranks": ["APO"],
              "schemes": ["A"]
            }
          }
        ]
      }
    ],
    
    "constraintList": [
      {
        "id": "apgdMaxWeeklyNormalHours",
        "type": "HARD",
        "params": {
          "maxNormalHours": 44.0
        }
      },
      {
        "id": "apgdMinRestBetweenShifts",
        "type": "HARD",
        "params": {
          "minRestMinutes": 480
        }
      }
    ],
    
    "solverConfig": {
      "timeLimitSeconds": 60
    }
  }
}
```

**Expected Results:**
- **Status:** OPTIMAL
- **Employees Used:** Minimum possible (2-3 employees)
- **Coverage:** 100%
- **Note:** Works well for simple shift coverage without rotation patterns

**⚠️ Warning:** Do NOT use this mode with rotation patterns (D-D-N-N-O-O) as it will cause offset clustering and INFEASIBLE results.

---

## Example 3: Testing Different Headcounts

**Scenario:** Scale testing with balanceWorkload mode

### Headcount = 1 (Small Scale)

Use the Example 1 JSON above with `headcount: 1` in demand shifts.

**Expected:**
- 3 employees used (rotations across offsets 0, 1, 2)
- 20-21 shifts per employee
- 100% utilization

### Headcount = 10 (Medium Scale)

Modify Example 1:
1. Change `headcount: 10` in demand shifts
2. Add 54 more employees (total 60) with round-robin offsets:
   - E007-E012: offsets 0-5
   - E013-E018: offsets 0-5
   - ...and so on

**Expected:**
- 30 employees used (5 per offset × 6 offsets)
- 20-21 shifts per employee
- 620 total assignments
- 100% utilization

### Headcount = 20 (Large Scale)

Modify Example 1:
1. Change `headcount: 20` in demand shifts
2. Add employees up to 120 total with round-robin offsets

**Expected:**
- 60 employees used (10 per offset × 6 offsets)
- 20-21 shifts per employee
- 1240 total assignments
- 100.2% efficiency

---

## Expected Results

### balanceWorkload Mode (Pattern-Based)

| Metric | Value |
|--------|-------|
| Status | OPTIMAL |
| Employee Utilization | 100% (all selected employees work full pattern) |
| Shifts per Employee | 20-21 per month (for D-D-N-N-O-O) |
| Coverage | 100% (all slots filled) |
| Efficiency | 100.0-100.2% |
| Unused Employees | 0 (no partial assignments) |
| Solve Time | 10-30 seconds (50-100 employees) |

### minimizeEmployeeCount Mode (Simple Coverage)

| Metric | Value |
|--------|-------|
| Status | OPTIMAL |
| Employee Utilization | Variable (may have 1-2 shift assignments) |
| Total Employees Used | Minimum possible |
| Coverage | 100% (all slots filled) |
| Note | Not recommended for rotation patterns |

---

## Troubleshooting

### INFEASIBLE Results

**Symptoms:**
- Solver status: INFEASIBLE
- No assignments generated
- Warnings about insufficient employees

**Causes & Solutions:**

1. **Insufficient employees for offset coverage**
   - Need at least 1-2 employees per offset (0-5)
   - Solution: Add more employees with distributed offsets

2. **Using minimizeEmployeeCount with patterns**
   - 100,000× weight causes offset clustering
   - Solution: Switch to `optimizationMode: "balanceWorkload"`

3. **Missing fixedRotationOffset flag**
   - Solver may re-cluster employees
   - Solution: Set `fixedRotationOffset: true`

4. **Constraint conflicts**
   - Gender, role, scheme mismatches
   - Solution: Review whitelist/blacklist settings

### Low Utilization (1-2 Shifts per Employee)

**Symptoms:**
- Many employees assigned
- Each employee works 1-5 shifts only
- Low efficiency (<50%)

**Cause:** Using minimizeEmployeeCount mode or continuous adherence disabled

**Solution:**
1. Switch to `optimizationMode: "balanceWorkload"`
2. Enable `fixedRotationOffset: true`
3. Ensure rotation patterns are defined

### Non-Deterministic Results

**Symptoms:**
- Different results on each run
- Slot count varies (e.g., 465 → 62 slots)

**Cause:** Solver exploring different offset assignments

**Solution:**
1. Set `fixedRotationOffset: true`
2. Pre-assign employee rotation offsets in input JSON
3. Use `balanceWorkload` mode for consistency

---

## Quick Reference

### When to Use balanceWorkload

✅ Pattern-based rotation schedules (D-D-N-N-O-O, D-D-D-D-O-O)  
✅ Need consistent employee utilization  
✅ Want fair workload distribution  
✅ Require continuous coverage with patterns  

### When to Use minimizeEmployeeCount

✅ Simple shift coverage without patterns  
✅ One-off or irregular scheduling  
✅ Emergency staffing with limited workforce  
❌ **NOT for pattern-based rotation**

### Essential Parameters for Patterns

```json
{
  "optimizationMode": "balanceWorkload",
  "fixedRotationOffset": true,
  "employees": [
    {"employeeId": "E001", "rotationOffset": 0},
    {"employeeId": "E002", "rotationOffset": 1},
    ...
  ],
  "demandItems": [{
    "shifts": [{
      "rotationSequence": ["D", "D", "N", "N", "O", "O"],
      "coverageAnchor": "2025-01-01"
    }]
  }]
}
```

---

**Last Updated:** January 12, 2025 (v0.7.3)
