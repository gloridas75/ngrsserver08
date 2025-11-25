# NGRS Solver API Quick Reference

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/version` | GET | API/solver version info |
| `/solve` | POST | Generate full roster (day-by-day assignments) |
| `/configure` | POST | **NEW**: Get optimal work patterns & staffing |

---

## Configuration Optimizer (ICPMP Tool)

### What It Does
Analyzes requirements and suggests:
1. Optimal work patterns (e.g., 4-on-2-off)
2. Minimum employee count needed
3. Rotation offsets for coverage diversity

### When to Use
- **Before** hiring: Determine staffing needs
- **Before** creating full roster: Validate patterns
- **For** cost estimation: Calculate labor costs
- **For** optimization: Find efficient rotations

---

## Quick Tests

### Test 1: Configuration Optimizer
```bash
curl -X POST http://127.0.0.1:8080/configure \
  -H "Content-Type: application/json" \
  -d @input/config_optimizer_test.json \
  | python -m json.tool
```

**Expected Result**:
- Status: 200 OK
- Total employees: 7
- Coverage: 100% for both requirements
- Response time: <5ms

### Test 2: Main Solver
```bash
curl -X POST http://127.0.0.1:8080/solve \
  -H "Content-Type: application/json" \
  -d @input/input_v0.7.json \
  | python -m json.tool
```

**Expected Result**:
- Status: 200 OK
- Assignments: 240
- Solver status: OPTIMAL
- Response time: 150-200ms

### Test 3: Health Check
```bash
curl http://127.0.0.1:8080/health
```

**Expected Result**:
```json
{"status": "ok"}
```

---

## Input Format Comparison

### `/configure` Input (Simplified)
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
      "shiftTypes": ["D"],
      "headcountPerDay": 2
    }
  ],
  "constraints": {
    "maxWeeklyNormalHours": 44
  }
}
```

### `/solve` Input (Full NGRS Schema)
```json
{
  "schemaVersion": "0.43",
  "planningHorizon": {...},
  "publicHolidays": [...],
  "shifts": [...],
  "employees": [...],          // Required
  "demands": [...],            // Required
  "constraints": {...}         // Full constraint set
}
```

---

## Output Comparison

### `/configure` Output
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
        "employeesRequired": 4
      },
      "coverage": {
        "expectedCoverageRate": 100.0
      }
    }
  ]
}
```

### `/solve` Output
```json
{
  "schemaVersion": "0.43",
  "solverRun": {
    "status": "OPTIMAL",
    "objectiveValue": 0
  },
  "score": {
    "hard": 0,
    "soft": 0
  },
  "assignments": [
    {
      "employeeId": "EMP001",
      "date": "2024-12-01",
      "demandId": "DEM001",
      "shiftCode": "D",
      "hours": {...}
    }
  ]
}
```

---

## Performance Metrics

| Endpoint | Complexity | Response Time | Use Case |
|----------|-----------|---------------|----------|
| `/configure` | Low | <5ms | Pre-planning |
| `/solve` | High | 150-500ms | Roster generation |

---

## Integration Workflow

```
┌─────────────────────┐
│  1. Configuration   │  → /configure → Optimal patterns + staffing
│     Optimization    │                 (7 employees, 4-on-2-off)
└─────────────────────┘
          ↓
┌─────────────────────┐
│  2. Review & Hire   │  → Review recommendations
│                     │  → Hire 7 employees
└─────────────────────┘
          ↓
┌─────────────────────┐
│  3. Roster          │  → /solve → Day-by-day assignments
│     Generation      │             (240 assignments)
└─────────────────────┘
```

---

## Sample Files

| File | Purpose | Size |
|------|---------|------|
| `input/config_optimizer_test.json` | Test `/configure` | 633 bytes |
| `input/requirements_simple.json` | Test `/configure` (5 req) | 2.0 KB |
| `input/input_v0.7.json` | Test `/solve` (full roster) | 25 KB |

---

## Documentation Files

| File | Description | Size |
|------|-------------|------|
| `CONFIGURATION_OPTIMIZER_API_TESTING.md` | Full testing guide | 15.3 KB |
| `CONFIGURATION_OPTIMIZER_API_SUMMARY.md` | Implementation summary | 12.8 KB |
| `API_VALIDATION_SUMMARY.md` | API validation report | 6.2 KB |

---

## Common Commands

### Start API Server
```bash
cd ngrssolver
python -m uvicorn src.api_server:app --host 127.0.0.1 --port 8080
```

### Stop API Server
```bash
pkill -f "uvicorn.*api_server"
```

### View Logs
```bash
tail -f api_server.log
```

### Test All Endpoints
```bash
# Health
curl http://127.0.0.1:8080/health

# Version
curl http://127.0.0.1:8080/version

# Configure
curl -X POST http://127.0.0.1:8080/configure \
  -d @input/config_optimizer_test.json

# Solve
curl -X POST http://127.0.0.1:8080/solve \
  -d @input/input_v0.7.json
```

---

## Status Summary

✅ **API Server**: Running on http://127.0.0.1:8080  
✅ **Configuration Optimizer**: `/configure` endpoint operational  
✅ **Main Solver**: `/solve` endpoint operational  
✅ **All Tests**: Passing (2/2 configuration tests, 1/1 solver test)  
✅ **Documentation**: Complete (3 docs, 34.3 KB total)  

---

## Key Differences: `/configure` vs `/solve`

| Feature | `/configure` | `/solve` |
|---------|--------------|----------|
| **Input Required** | Requirements only | Full NGRS input |
| **Employee List** | ❌ Not needed | ✅ Required |
| **Output** | Patterns & counts | Day-by-day assignments |
| **Speed** | <5ms | 150-500ms |
| **Constraints** | 4 basic | 15 hard constraints |
| **Use Case** | Pre-planning | Actual roster |

---

## Next Steps

1. **For Configuration**: Use `/configure` to determine staffing needs
2. **For Roster**: Use `/solve` to generate actual assignments
3. **For Validation**: Compare both outputs to verify consistency

**All systems operational and tested.** ✅
