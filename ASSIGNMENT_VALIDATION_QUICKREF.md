# Assignment Validation - Quick Reference

## 🚀 Quick Start (30 seconds)

### 1. Start Server
```bash
uvicorn src.api_server:app --reload --port 8080
```

### 2. Test Endpoint
```bash
curl -X POST http://localhost:8080/validate/assignment \
  -H "Content-Type: application/json" \
  -d '{
    "employee": {
      "employeeId": "EMP001",
      "rank": "SO",
      "gender": "M",
      "scheme": "A",
      "productTypes": ["Guarding"]
    },
    "existingAssignments": [],
    "candidateSlots": [{
      "slotId": "slot_123",
      "startDateTime": "2026-01-15T07:00:00+08:00",
      "endDateTime": "2026-01-15T15:00:00+08:00",
      "shiftType": "DAY"
    }]
  }'
```

### 3. Run Tests
```bash
python test_assignment_validation.py
```

---

## 📋 Minimal Request

```json
{
  "employee": {
    "employeeId": "EMP001",
    "rank": "SO",
    "gender": "M",
    "scheme": "A"
  },
  "existingAssignments": [],
  "candidateSlots": [{
    "slotId": "slot_123",
    "startDateTime": "2026-01-15T07:00:00+08:00",
    "endDateTime": "2026-01-15T15:00:00+08:00",
    "shiftType": "DAY"
  }]
}
```

---

## ✅ Response: Feasible

```json
{
  "status": "success",
  "validationResults": [{
    "slotId": "slot_123",
    "isFeasible": true,
    "violations": [],
    "recommendation": "feasible"
  }],
  "employeeId": "EMP001",
  "timestamp": "2026-01-14T10:30:00",
  "processingTimeMs": 12.5
}
```

---

## ❌ Response: Not Feasible

```json
{
  "status": "success",
  "validationResults": [{
    "slotId": "slot_123",
    "isFeasible": false,
    "violations": [{
      "constraintId": "C2",
      "constraintName": "Weekly Hours Cap",
      "violationType": "hard",
      "description": "Weekly normal hours 56.0h exceeds cap of 52.0h",
      "context": {
        "weeklyHours": 56.0,
        "weeklyCap": 52.0,
        "weekStart": "2026-01-12",
        "weekEnd": "2026-01-18"
      }
    }],
    "recommendation": "not_feasible"
  }],
  "employeeId": "EMP001",
  "timestamp": "2026-01-14T10:32:15",
  "processingTimeMs": 18.3
}
```

---

## 🔍 What Gets Checked

| Constraint | Limit | Description |
|------------|-------|-------------|
| **C1** | 14h/13h/9h | Daily hours by scheme |
| **C2** | 52h/week | Weekly normal hours |
| **C3** | 12 days | Consecutive work days |
| **C4** | 12h | Rest between shifts |
| **C17** | 72h/month | Monthly overtime |

---

## 🎯 Use Cases

### ✅ Web UI Manual Assignment
User wants to assign employee to unassigned slot → validate first

### ✅ Bulk Assignment Check
Check if employee can work multiple slots at once

### ✅ What-If Analysis
"Can this employee work these shifts without violations?"

### ❌ Team Constraints
Cannot check C9 (team) or C14 (quotas) - needs global context

---

## 📁 Files

```
src/assignment_validator.py          # Core logic
src/models.py                         # Pydantic models (updated)
src/api_server.py                     # API endpoint (updated)
test_assignment_validation.py         # Test suite
ASSIGNMENT_VALIDATION_FEATURE.md      # Full docs
```

---

## 🐛 Troubleshooting

### Import Error
```bash
# Make sure you're in the right directory
cd /path/to/ngrssolver
python -c "from src.assignment_validator import AssignmentValidator"
```

### 404 Not Found
```bash
# Check server is running
curl http://localhost:8080/health

# Check docs
open http://localhost:8080/docs
```

### Validation Always Fails
```bash
# Check constraint configuration
# Set constraintList to enable/disable specific constraints
{
  "constraintList": [
    {"constraintId": "C1", "enabled": false}  # Disable C1
  ]
}
```

---

## 🚀 Production Endpoint

```bash
curl -X POST https://ngrssolver09.comcentricapps.com/validate/assignment \
  -H "Content-Type: application/json" \
  -d @request.json
```

---

## 📊 Performance

- **Target:** <100ms for single slot
- **Typical:** 10-20ms for 1 slot, 50-100ms for 5 slots
- **Max:** 200ms for 10 slots

---

## ⚡ Tips

1. **Batch Validation** - Send multiple slots in one request
2. **Minimal Data** - Only required fields needed for fast response
3. **Async Not Needed** - Response is synchronous (<100ms)
4. **Error Messages** - Check `violations[].description` for details
5. **Context Data** - Use `violations[].context` for numeric details

---

## 📞 Need Help?

- **Full Docs:** [ASSIGNMENT_VALIDATION_FEATURE.md](ASSIGNMENT_VALIDATION_FEATURE.md)
- **API Docs:** http://localhost:8080/docs
- **Tests:** `python test_assignment_validation.py`

---

✅ **Ready to Use!**
