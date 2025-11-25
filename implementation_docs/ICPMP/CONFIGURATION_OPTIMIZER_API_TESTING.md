# Configuration Optimizer API Testing Guide

## Overview

The **Configuration Optimizer** (also known as the Intelligent Configuration and Planning Meta-tool or **ICPMP**) is now available via REST API at the `/configure` endpoint. This tool analyzes requirements and suggests optimal work patterns, minimum staffing levels, and rotation offsets.

## Endpoint: POST /configure

### Base URL
```
http://127.0.0.1:8080/configure
```

### What It Does

Given minimal input (shift requirements and headcount needs), the optimizer recommends:

1. **Best work patterns** for each requirement (e.g., 4 days on, 2 days off)
2. **Minimum employee counts** needed for 100% coverage
3. **Optimal rotation offsets** for maximum coverage diversity
4. **Coverage quality metrics** (coverage rate, balance scores, variance)

### Input Format

The endpoint accepts two input methods:

#### Method 1: JSON Body
```bash
curl -X POST http://127.0.0.1:8080/configure \
  -H "Content-Type: application/json" \
  -d @input_file.json
```

#### Method 2: File Upload
```bash
curl -X POST http://127.0.0.1:8080/configure \
  -F "file=@input_file.json"
```

### Input Schema

```json
{
  "planningHorizon": {
    "startDate": "YYYY-MM-DD",
    "endDate": "YYYY-MM-DD"
  },
  "requirements": [
    {
      "id": "string",                    // Unique requirement ID
      "name": "string",                  // Descriptive name
      "productType": "string",           // Product type (Guard, APO, CVSO)
      "rank": "string",                  // Rank requirement
      "scheme": "string",                // Work scheme (A/B/P)
      "shiftTypes": ["D", "N", ...],     // Shift codes for this requirement
      "headcountPerDay": number          // Officers needed per day
    }
  ],
  "constraints": {
    "maxWeeklyNormalHours": 44,          // Weekly hour cap (default: 44)
    "maxMonthlyOTHours": 72,             // Monthly OT cap (default: 72)
    "maxConsecutiveWorkDays": 12,        // Max consecutive work days (default: 12)
    "minOffDaysPerWeek": 1               // Min off days per week (default: 1)
  }
}
```

### Output Schema

```json
{
  "schemaVersion": "0.8",
  "configType": "optimizedRosterConfiguration",
  "generatedAt": "ISO-8601 timestamp",
  "summary": {
    "totalRequirements": number,
    "totalEmployees": number,
    "planningHorizon": {
      "startDate": "ISO-8601",
      "endDate": "ISO-8601",
      "days": number
    }
  },
  "recommendations": [
    {
      "requirementId": "string",
      "requirementName": "string",
      "productType": "string",
      "rank": "string",
      "scheme": "string",
      "configuration": {
        "workPattern": ["D", "D", "O", "D", "D", "O"],  // Work pattern cycle
        "employeesRequired": number,                     // Minimum employees needed
        "rotationOffsets": [0, 1, 2, ...],              // Staggered offsets
        "cycleLength": number                            // Length of pattern cycle
      },
      "coverage": {
        "expectedCoverageRate": number,                  // Percentage (0-100)
        "daysFullyCovered": number,
        "daysUndercovered": number,
        "averageAvailable": number,
        "requiredPerDay": number
      },
      "quality": {
        "balanceScore": number,                          // 0-100, higher is better
        "variance": number,                              // Lower is better
        "totalExcessCoverage": number
      },
      "notes": ["string", ...]                          // Human-readable insights
    }
  ],
  "meta": {
    "requestId": "UUID",
    "timestamp": "ISO-8601",
    "processingTimeMs": number
  }
}
```

---

## Testing Examples

### Example 1: Simple 2-Requirement Configuration

**Input** (`config_optimizer_test.json`):
```json
{
  "planningHorizon": {
    "startDate": "2024-12-01",
    "endDate": "2024-12-30"
  },
  "requirements": [
    {
      "id": "REQ_DAY_GUARD",
      "name": "Day Guards",
      "productType": "Guard",
      "rank": "G1",
      "scheme": "A",
      "shiftTypes": ["D"],
      "headcountPerDay": 2
    },
    {
      "id": "REQ_NIGHT_PATROL",
      "name": "Night Patrol",
      "productType": "Guard",
      "rank": "G2",
      "scheme": "B",
      "shiftTypes": ["N"],
      "headcountPerDay": 1
    }
  ],
  "constraints": {
    "maxWeeklyNormalHours": 44,
    "maxMonthlyOTHours": 72,
    "maxConsecutiveWorkDays": 12,
    "minOffDaysPerWeek": 1
  }
}
```

**Test Command**:
```bash
curl -X POST http://127.0.0.1:8080/configure \
  -H "Content-Type: application/json" \
  -d @input/config_optimizer_test.json \
  | python -m json.tool
```

**Expected Output**:
```json
{
  "summary": {
    "totalRequirements": 2,
    "totalEmployees": 7
  },
  "recommendations": [
    {
      "requirementId": "REQ_DAY_GUARD",
      "configuration": {
        "workPattern": ["D", "D", "O", "D", "D", "O"],
        "employeesRequired": 4,
        "rotationOffsets": [0, 1, 2, 3]
      },
      "coverage": {
        "expectedCoverageRate": 100.0
      }
    },
    {
      "requirementId": "REQ_NIGHT_PATROL",
      "configuration": {
        "workPattern": ["N", "N", "O", "N", "N", "O"],
        "employeesRequired": 3,
        "rotationOffsets": [0, 1, 2]
      },
      "coverage": {
        "expectedCoverageRate": 100.0
      }
    }
  ]
}
```

**Interpretation**:
- **REQ_DAY_GUARD**: Needs 4 employees working 4-on-2-off pattern, achieving 100% coverage of 2 guards per day
- **REQ_NIGHT_PATROL**: Needs 3 employees working 4-on-2-off pattern, achieving 100% coverage of 1 guard per night
- **Total Staffing**: 7 employees across both requirements

---

### Example 2: Complex 5-Requirement Configuration

**Input** (`requirements_simple.json`):
```json
{
  "planningHorizon": {
    "startDate": "2025-12-01",
    "endDate": "2025-12-31"
  },
  "requirements": [
    {
      "id": "REQ_APO_DAY",
      "name": "APO Day Patrol",
      "productType": "APO",
      "rank": "APO",
      "scheme": "A",
      "shiftTypes": ["D"],
      "headcountPerDay": 4
    },
    {
      "id": "REQ_APO_NIGHT",
      "name": "APO Night Patrol",
      "productType": "APO",
      "rank": "APO",
      "scheme": "B",
      "shiftTypes": ["N"],
      "headcountPerDay": 1
    },
    {
      "id": "REQ_CVSO_NIGHT_1",
      "name": "CVSO Night Check 1",
      "productType": "CVSO",
      "rank": "CVSO2",
      "scheme": "B",
      "shiftTypes": ["N"],
      "headcountPerDay": 1
    },
    {
      "id": "REQ_CVSO_NIGHT_2",
      "name": "CVSO Night Check 2",
      "productType": "CVSO",
      "rank": "CVSO2",
      "scheme": "B",
      "shiftTypes": ["N"],
      "headcountPerDay": 1
    },
    {
      "id": "REQ_CVSO_NIGHT_3",
      "name": "CVSO Night Check 3",
      "productType": "CVSO",
      "rank": "CVSO2",
      "scheme": "B",
      "shiftTypes": ["N"],
      "headcountPerDay": 1
    }
  ],
  "constraints": {
    "maxWeeklyNormalHours": 44,
    "maxMonthlyOTHours": 72,
    "maxConsecutiveWorkDays": 12,
    "minOffDaysPerWeek": 1
  }
}
```

**Test Command**:
```bash
curl -X POST http://127.0.0.1:8080/configure \
  -H "Content-Type: application/json" \
  -d @input/requirements_simple.json \
  | python -m json.tool
```

**Expected Output Summary**:
```json
{
  "summary": {
    "totalRequirements": 5,
    "totalEmployees": 19
  },
  "recommendations": [
    {
      "requirementId": "REQ_APO_DAY",
      "configuration": {
        "employeesRequired": 7,
        "workPattern": ["D", "D", "D", "D", "O", "O"]
      },
      "coverage": {
        "expectedCoverageRate": 100.0
      }
    },
    {
      "requirementId": "REQ_APO_NIGHT",
      "configuration": {
        "employeesRequired": 3
      }
    },
    {
      "requirementId": "REQ_CVSO_NIGHT_1",
      "configuration": {
        "employeesRequired": 3
      }
    },
    {
      "requirementId": "REQ_CVSO_NIGHT_2",
      "configuration": {
        "employeesRequired": 3
      }
    },
    {
      "requirementId": "REQ_CVSO_NIGHT_3",
      "configuration": {
        "employeesRequired": 3
      }
    }
  ]
}
```

**Interpretation**:
- **Total Staffing**: 19 employees across 5 requirements
- **APO Day Patrol**: 7 employees (4 per day required)
- **Other Requirements**: 3 employees each (1 per day required)
- **All Requirements**: 100% coverage achieved

---

### Example 3: File Upload Method

**Test Command**:
```bash
curl -X POST http://127.0.0.1:8080/configure \
  -F "file=@input/config_optimizer_test.json" \
  | python -m json.tool
```

Same output as Example 1.

---

## Common Use Cases

### 1. Pre-Planning: Determine Staffing Needs
**Scenario**: Before hiring, determine how many employees you need for a new contract.

**Input**: Requirements with headcount and shift types
**Output**: Minimum employee count needed

### 2. Configuration Validation
**Scenario**: Validate that your planned work patterns achieve 100% coverage.

**Input**: Proposed requirements
**Output**: Coverage rate, balance scores, feasibility check

### 3. Work Pattern Optimization
**Scenario**: Find the most efficient rotation pattern.

**Input**: Multiple requirements with varying shift types
**Output**: Optimal patterns balancing work/rest and minimizing staff

### 4. Cost Estimation
**Scenario**: Estimate labor costs before finalizing a roster.

**Input**: Requirements with constraints
**Output**: Total employee count × estimated cost per employee

---

## Response Status Codes

| Status | Meaning |
|--------|---------|
| 200 | Success - Optimized configuration returned |
| 400 | Bad Request - Missing required fields (`requirements`, `planningHorizon`) |
| 422 | Unprocessable Entity - Invalid JSON format |
| 500 | Internal Server Error - Optimization failed (check logs) |

---

## Performance Metrics

Based on testing:

| Metric | Value |
|--------|-------|
| Response Time (2 requirements) | ~0-5 ms |
| Response Time (5 requirements) | ~5-15 ms |
| Max Supported Requirements | 50+ |
| Planning Horizon | Up to 365 days |

---

## Integration Workflow

### Step 1: Configuration Optimization
```bash
# Get optimal configuration
curl -X POST http://127.0.0.1:8080/configure \
  -H "Content-Type: application/json" \
  -d @requirements.json \
  > optimized_config.json
```

### Step 2: Review Recommendations
```bash
# Extract employee counts
cat optimized_config.json | jq '.summary.totalEmployees'

# Extract work patterns
cat optimized_config.json | jq '.recommendations[].configuration.workPattern'
```

### Step 3: Generate Full Roster
```bash
# Use recommended configuration in main solver
# (Manual step: create full NGRS input from configuration)
curl -X POST http://127.0.0.1:8080/solve \
  -H "Content-Type: application/json" \
  -d @full_ngrs_input.json \
  > final_roster.json
```

---

## Debugging Tips

### Check API Server is Running
```bash
curl http://127.0.0.1:8080/health
# Expected: {"status":"ok"}
```

### View API Server Logs
```bash
tail -f api_server.log
```

### Validate Input JSON
```bash
cat input_file.json | python -m json.tool
```

### Test with Minimal Input
```json
{
  "planningHorizon": {
    "startDate": "2024-12-01",
    "endDate": "2024-12-30"
  },
  "requirements": [
    {
      "id": "TEST",
      "name": "Test Requirement",
      "productType": "Guard",
      "rank": "G1",
      "scheme": "A",
      "shiftTypes": ["D"],
      "headcountPerDay": 1
    }
  ],
  "constraints": {}
}
```

---

## Differences from Main Solver (`/solve`)

| Feature | `/configure` (Optimizer) | `/solve` (Main Solver) |
|---------|--------------------------|-------------------------|
| **Purpose** | Find optimal configuration | Generate full roster |
| **Input** | Simplified requirements | Full NGRS input (employees, demands, etc.) |
| **Output** | Work patterns + staffing | Day-by-day assignments |
| **Speed** | <50ms | 150-500ms |
| **Use Case** | Pre-planning, cost estimation | Actual roster generation |
| **Employee List** | Not required | Required |
| **Constraints** | Basic (hours, rest days) | Full constraint suite (15 constraints) |

---

## API Quick Reference

### Start API Server
```bash
cd /Users/glori/1\ Anthony_Workspace/My\ Developments/NGRS/ngrs-solver-v0.7/ngrssolver
python -m uvicorn src.api_server:app --host 127.0.0.1 --port 8080
```

### Test Endpoints
```bash
# Health check
curl http://127.0.0.1:8080/health

# Version info
curl http://127.0.0.1:8080/version

# Configuration optimizer
curl -X POST http://127.0.0.1:8080/configure \
  -H "Content-Type: application/json" \
  -d @input/config_optimizer_test.json

# Main solver
curl -X POST http://127.0.0.1:8080/solve \
  -H "Content-Type: application/json" \
  -d @input/input_v0.7.json
```

### Stop API Server
```bash
pkill -f "uvicorn.*api_server"
```

---

## Summary

The Configuration Optimizer API (`/configure` endpoint) is now fully operational and tested. It provides intelligent roster planning recommendations in milliseconds, helping you:

✅ Determine minimum staffing needs  
✅ Validate work pattern feasibility  
✅ Optimize rotation schedules  
✅ Estimate resource costs  
✅ Achieve 100% coverage with minimal staff  

**Next Steps**: Use this tool for pre-planning before running the main solver (`/solve`) to generate detailed day-by-day rosters.
