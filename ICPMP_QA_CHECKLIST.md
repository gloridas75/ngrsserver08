# ICPMP Quality Assurance Checklist

## Pre-Deployment Testing Checklist

Before pushing any ICPMP changes to production, verify ALL of these:

### 1. Output Schema Completeness
- [ ] `expectedCoverageRate` has meaningful value (not 0)
- [ ] `coverageType` matches expectedCoverageRate (>= 100% = "complete", < 100% = "partial")
- [ ] `employeesRequired` is populated
- [ ] `strictEmployees` + `flexibleEmployees` = `employeesRequired`
- [ ] `employeeOffsets` array length matches `employeesRequired`
- [ ] `workPattern` array length matches `coverageDays` length
- [ ] `score` is present and reasonable
- [ ] `alternativeRank` is sequential (1, 2, 3, ...)

### 2. API Response Validation
- [ ] API returns 200 status (not 500)
- [ ] Response contains `summary` object with:
  - [ ] `totalRequirements`
  - [ ] `totalEmployees`
  - [ ] `optimizerVersion` (should be "ICPMP v2.0 (Enhanced)")
- [ ] Response contains `recommendations[]` array
- [ ] Each recommendation has all required fields

### 3. Local Testing
Run these tests BEFORE pushing:

```bash
# Test 1: Local ICPMP v2 test
python test_icpmp_v2_test2.py

# Test 2: Check output has expectedCoverageRate
cat output/icpmp_v2_test2_result_*.json | grep expectedCoverageRate
# Should NOT show 0.0 for all results

# Test 3: Verify coverage calculation
# For 5/2 pattern (5 work, 2 off) with 30 headcount:
# 42 employees × (5/7) = 30 coverage → 100%
```

### 4. Production Testing
After deploying to production:

```bash
# From local machine
./test_production_icpmp.sh

# Manual test
curl -X POST https://ngrssolver09.comcentricapps.com/configure \
  -H "Content-Type: application/json" \
  -d @output/icpmp_v2_test2.json \
  | python3 -m json.tool \
  | grep -A 3 "expectedCoverageRate"
```

---

## Common Issues & Solutions

### Issue 1: expectedCoverageRate showing 0.0

**Symptom:**
```json
"coverage": {
  "expectedCoverageRate": 0.0,
  "coverageType": "partial"
}
```

**Root Causes:**
1. **Fallback calculation returning (0, 0) for coverageRange**
   - Fix: Calculate expected_daily_coverage in fallback
   - Formula: `employees × (work_days_in_cycle / cycle_length)`

2. **Malformed ternary expression in format_output_config**
   - Fix: Use proper if/else blocks instead of inline ternary

3. **Preprocessing simulation failing silently**
   - Check logs for "Preprocessing simulation failed"
   - Ensure fallback calculation is robust

**Prevention:**
- Always test fallback code paths
- Add unit tests for coverage calculation
- Log calculation inputs/outputs for debugging

### Issue 2: API parameter mismatch

**Symptom:**
```
"list indices must be integers or slices, not str"
```

**Root Cause:**
API passing wrong parameter type to functions (e.g., array instead of dict)

**Solution:**
```python
# WRONG
output_config = format_output_config(result, config["requirements"])

# RIGHT
output_config = format_output_config(result, config)  # Pass full config
```

**Prevention:**
- Check function signatures before calling
- Use type hints in function definitions
- Test API endpoints after code changes

### Issue 3: Missing imports

**Symptom:**
```
NameError: name 'List' is not defined
```

**Root Cause:**
Using type hints without importing from `typing`

**Solution:**
```python
from typing import List, Optional, Dict
```

**Prevention:**
- Run syntax checks before committing: `python3 -m py_compile file.py`
- Use the deployment scripts that include syntax validation

---

## Code Review Checklist

When reviewing ICPMP changes, verify:

### Data Flow
- [ ] Input validation: Check all required fields are present
- [ ] Data transformation: Verify field name mappings (headcountByShift vs headcountPerShift)
- [ ] Output formatting: Ensure all output fields are populated
- [ ] Error handling: Check fallback calculations are complete

### Calculations
- [ ] Coverage calculation formula is correct
- [ ] Employee count formula is correct
- [ ] Pattern length matches coverage days
- [ ] Offset distribution is within valid range

### Backwards Compatibility
- [ ] API accepts both old and new field names
- [ ] Output schema version is incremented if changed
- [ ] Existing tests still pass
- [ ] Documentation is updated

---

## Automated Testing Strategy

### Unit Tests (To Be Implemented)
```python
# tests/test_config_optimizer.py
def test_coverage_calculation():
    """Test expectedCoverageRate is calculated correctly"""
    pattern = ['D', 'D', 'D', 'D', 'D', 'O', 'O']
    headcount = 30
    employees = 42
    
    # Expected: 42 × (5/7) = 30 → 100%
    result = calculate_coverage(pattern, employees, headcount)
    assert result['expectedCoverageRate'] == 100.0
    assert result['coverageType'] == 'complete'

def test_fallback_coverage():
    """Test fallback calculation populates coverageRange"""
    # Simulate preprocessing failure
    result = simulate_coverage_fallback(
        pattern=['D', 'D', 'D', 'D', 'D', 'O', 'O'],
        headcount=30
    )
    
    assert result['coverageRange'] != (0, 0)
    assert result['coverageRange'][0] > 0
    assert result['coverageRange'][1] > 0
```

### Integration Tests
```python
# tests/test_icpmp_api.py
def test_configure_endpoint_coverage():
    """Test /configure endpoint returns valid expectedCoverageRate"""
    response = client.post("/configure", json=test_input)
    
    assert response.status_code == 200
    data = response.json()
    
    for rec in data['recommendations']:
        coverage_rate = rec['coverage']['expectedCoverageRate']
        assert coverage_rate > 0, "expectedCoverageRate must be > 0"
        assert coverage_rate <= 100, "expectedCoverageRate must be <= 100"
```

### Regression Tests
Create regression test suite with known good outputs:
```bash
# tests/regression/
├── input_scenario_1.json
├── expected_output_1.json
├── input_scenario_2.json
├── expected_output_2.json
```

Run before each release:
```bash
python tests/regression_test.py --compare-outputs
```

---

## Deployment Best Practices

### Before Committing
1. Run local tests
2. Check syntax: `python3 -m py_compile $(git diff --name-only '*.py')`
3. Review diff carefully for unintended changes
4. Update version number if API contract changes

### Before Pushing
1. Ensure all tests pass
2. Update CHANGELOG.md
3. Tag commit if it's a release: `git tag v0.96.1`

### After Deploying
1. Run production smoke tests
2. Monitor logs for errors
3. Check health endpoint
4. Test key endpoints with sample data

### Rollback Plan
Always know the last working commit:
```bash
# On production server
cd /opt/ngrs-solver
git log --oneline -n 5  # Note last working commit

# If issue found
git checkout <last-working-commit>
./quick_restart.sh
```

---

## Monitoring & Alerts

### Key Metrics to Monitor
- **expectedCoverageRate = 0**: Should trigger alert
- **API 500 errors**: Should trigger immediate alert
- **Processing time > 30s**: Performance degradation
- **Unassigned slots > 50%**: Likely infeasible input

### Log Monitoring
Search for these patterns:
```bash
# Error patterns
grep -i "error" /var/log/ngrs-solver.log
grep -i "failed" /var/log/ngrs-solver.log
grep "expectedCoverageRate.*0\.0" /var/log/ngrs-solver.log

# Success patterns
grep "OPTIMIZATION COMPLETE" /var/log/ngrs-solver.log
grep "✓ Extracted" /var/log/ngrs-solver.log
```

---

## Documentation Standards

### Code Comments
- **Purpose**: Why this code exists
- **Assumptions**: What inputs are expected
- **Edge Cases**: Known limitations or special handling
- **Examples**: Sample input/output

### API Documentation
Update whenever:
- Input schema changes
- Output schema changes
- New features added
- Behavior changes

### Version History
Document in CHANGELOG.md:
```markdown
## [0.96.1] - 2025-12-08
### Fixed
- expectedCoverageRate now calculated correctly (was 0.0)
- Fallback calculation populates proper coverageRange
```

---

## Contact & Support

**Issues Found?**
1. Check this checklist first
2. Review recent commits: `git log --oneline -n 10`
3. Check logs: `tail -100 /var/log/ngrs-solver.log`
4. Use deployment scripts for safe restart

**Critical Bug Process:**
1. Roll back to last working version immediately
2. Document the issue
3. Fix locally with tests
4. Deploy with validation

---

## Summary

**Golden Rules:**
1. ✅ **Test locally before pushing**
2. ✅ **Validate ALL output fields**
3. ✅ **Check fallback code paths**
4. ✅ **Use deployment scripts**
5. ✅ **Monitor production after deploy**

**Remember:** A missing or incorrect `expectedCoverageRate` makes ICPMP results meaningless to users. Always validate this field!
