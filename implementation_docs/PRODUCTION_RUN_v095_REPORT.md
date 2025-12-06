# Production Run Report - v0.95
**Date:** December 6, 2025  
**Job ID:** b5f9e990-0f3f-490b-a9f6-1bc30fac4bf0  
**Environment:** Production (ngrssolver08.comcentricapps.com)

---

## Executive Summary

Successfully deployed and validated v0.95 on production with a real-world scheduling scenario involving **102 employees** across **31 days** with **2 shift requirements**. The solver achieved an **OPTIMAL solution** in **133.7 seconds** with **100% demand coverage**.

---

## Input Specifications

### Scenario Details
- **Input File:** `AUTO-20251206-233E7006_Solver_Input.json`
- **Planning Period:** March 1-31, 2026 (31 days)
- **Employee Pool:** 102 employees
- **Requirements:** 2 shift patterns

### Shift Requirements
1. **Requirement 52_1:**
   - Headcount: 10 per day
   - Pattern: [D, D, D, O, O, D, D] (7-day cycle)
   - Employees Required: 18-22

2. **Requirement 53_1:**
   - Headcount: 15 per day
   - Pattern: [D, D, D, D, O, D, D] (7-day cycle)
   - Employees Required: 27-33

### Feasibility Check
- **Status:** Likely Feasible (High Confidence)
- **Employees Provided:** 102
- **Employees Required:** 45-55
- **Shortfall:** 0 ✓

---

## Solution Results

### Solver Performance
```
Status:          OPTIMAL ⭐
Quality Grade:   OPTIMAL
Solve Time:      133.7 seconds
Version:         optSolve-py-0.95.0
Schema:          0.95
```

### Coverage Metrics
```
Total Slots:     685
Assigned:        685 (100%)
Unfilled:        0
Coverage Rate:   100%
```

### Employee Utilization
```
Available:       102 employees
Used:            41 employees (40.2%)
Unused:          61 employees
```

---

## v0.95 Features Validation

### ✅ 1. patternDay Field in Assignments
- **Total Assignments:** 685
- **With patternDay:** 685 (100%)
- **Formula:** `(days_since_start + rotationOffset) % patternLength`

**Sample Assignments:**
```
Emp:00073354 | 2026-03-02 | Req:52_1 | patternDay:5
Emp:00158151 | 2026-03-03 | Req:52_1 | patternDay:0
Emp:00073354 | 2026-03-04 | Req:52_1 | patternDay:0
```

### ✅ 2. patternDay in employeeRoster
- **Applies to:** ASSIGNED and OFF_DAY statuses only
- **Sample Employee:** 00027821
  - ASSIGNED (with patternDay): 22 days
  - OFF_DAY (with patternDay): 9 days

### ✅ 3. rosterSummary Block
- **Total Daily Statuses:** 3,162 (102 employees × 31 days)

**Status Breakdown:**
```
ASSIGNED:    685 (21.7%) - Working shifts with patternDay
OFF_DAY:     288 ( 9.1%) - Pattern rest days with patternDay
UNASSIGNED:  298 ( 9.4%) - Available but not scheduled
NOT_USED:  1,891 (59.8%) - Employees not in rotation
```

### ✅ 4. Removed Redundant Fields
All removed successfully:
- ❌ `shiftId` - Removed
- ❌ `constraintResults` - Removed
- ❌ `workPattern` array - Removed

**File Size Optimization:**
- Previous: ~487 KB (with redundant fields)
- Current: 724 KB (larger due to employeeRoster expansion)
- **Note:** employeeRoster now includes all 102 employees × 31 days = 3,162 daily status entries

---

## Output Analysis

### File Details
```
Filename:  AUTO-20251206-233E7006_Production_Result_v095.json
Size:      741,472 bytes (724.1 KB)
Location:  output/
```

### Data Structure
```json
{
  "schemaVersion": "0.95",
  "solutionQuality": {
    "solverStatus": "OPTIMAL",
    "qualityGrade": "OPTIMAL",
    "coverageMetrics": {...},
    "employeeUtilization": {...}
  },
  "assignments": [685 items with patternDay],
  "employeeRoster": [102 employees with daily status],
  "rosterSummary": {
    "totalDailyStatuses": 3162,
    "byStatus": {...}
  },
  "solverRun": {...},
  "meta": {...}
}
```

---

## Deployment Verification

### Production Environment
- **Server:** EC2 (ip-172-31-25-77)
- **URL:** https://ngrssolver08.comcentricapps.com
- **Docker Container:** ngrs-solver-api (eb4422bffcc0)
- **Status:** Healthy ✓
- **Version:** v0.95

### API Endpoints Tested
- ✅ `POST /solve/async` - Job submission (used for this run)
- ✅ `GET /solve/async/{job_id}` - Status check
- ✅ `GET /solve/async/{job_id}/result` - Results retrieval
- ✅ `GET /health` - Health check
- ✅ `GET /version` - Version info

---

## Key Improvements in v0.95

1. **Pattern Day Tracking**
   - Every assignment now includes its position in the work pattern (0-6)
   - Enables easy verification of pattern compliance
   - Facilitates rotation management

2. **Enhanced Employee Roster**
   - Added patternDay to ASSIGNED and OFF_DAY entries
   - Clear distinction between pattern-based statuses and availability

3. **Roster Summary Statistics**
   - Quick overview of scheduling distribution
   - Helps identify utilization patterns
   - Useful for capacity planning

4. **Code Optimization**
   - Removed 3 redundant fields from assignments
   - Cleaner, more maintainable output structure
   - Improved API response clarity

---

## Test Scenario Complexity

### Challenge Factors
- **Scale:** 102 employees × 31 days = 3,162 employee-days
- **Requirements:** 685 total shift slots to fill
- **Patterns:** 2 different 7-day rotation patterns
- **Constraints:** Employee availability, pattern compliance, demand coverage

### Solution Quality
- **Optimal:** Mathematical proof of best solution
- **Complete Coverage:** 100% of demand met
- **Efficient:** 40.2% employee utilization (optimal for given demand)
- **Fast:** 133.7 seconds for complex optimization

---

## Production Deployment Timeline

1. **Development Phase**
   - Added patternDay field to assignments
   - Fixed calculation formula
   - Added employeeRoster enhancements
   - Added rosterSummary block
   - Removed redundant fields

2. **Testing Phase**
   - Local validation with test data
   - Formula verification against Excel
   - Field presence verification
   - File size optimization check

3. **Deployment Phase**
   - Code committed to GitHub (commit: 07339bc)
   - Docker image rebuilt with v0.95
   - Container deployed to production
   - Health checks verified

4. **Production Validation**
   - Real-world scenario executed
   - All v0.95 features confirmed
   - Performance metrics validated
   - Output quality verified

---

## Recommendations

### For Future Use
1. **Time Limits:** For large scenarios (100+ employees, 30+ days), use `/solve/async` endpoint
2. **Monitoring:** Poll job status every 10-30 seconds
3. **Output Storage:** Save results to output/ folder for analysis

### Performance Expectations
- **Small** (20 employees, 7 days): 1-5 seconds
- **Medium** (50 employees, 14 days): 5-30 seconds
- **Large** (100 employees, 31 days): 60-180 seconds
- **Extra Large** (200+ employees, 31+ days): 180-600 seconds

---

## Conclusion

✅ **v0.95 successfully deployed and validated in production**

All new features are working as designed:
- patternDay calculation accurate across all assignments
- employeeRoster enhanced with pattern information
- rosterSummary providing valuable insights
- Redundant fields successfully removed
- OPTIMAL solution quality maintained

The production run demonstrates the solver's capability to handle real-world scheduling scenarios with 100% demand coverage and optimal resource utilization.

---

## Related Documentation
- [DEPLOYMENT_v0.95.md](DEPLOYMENT_v0.95.md) - Deployment guide
- [AWS_APPRUNNER_QUICK_REF.md](AWS_APPRUNNER_QUICK_REF.md) - API reference
- [API_QUICK_REFERENCE.md](API_QUICK_REFERENCE.md) - API endpoints

## Output Files
- Input: `input/AUTO-20251206-233E7006_Solver_Input.json`
- Output: `output/AUTO-20251206-233E7006_Production_Result_v095.json`
