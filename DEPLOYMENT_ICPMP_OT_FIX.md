# DEPLOYMENT GUIDE: ICPMP OT Capacity Fix

## Summary
Fixed ICPMP to read scheme-specific monthly OT capacities from input configuration instead of hard-coding 72h for all schemes.

**Commit**: 551c141 "Fix ICPMP: Make monthly OT capacity scheme-aware"

## Problem Fixed
- **Before**: ICPMP hard-coded 72h monthly OT for all schemes
- **Impact**: Scheme A + APO has 124h OT → 72% capacity underestimation → over-selected employees (e.g., 21 vs 17)
- **Result**: Over-subscription caused INFEASIBLE despite surplus capacity

## Changes Made
1. **icpmp_integration.py**: 
   - Added `_get_monthly_ot_cap()` method to extract OT limits from input
   - Passes `monthly_ot_cap` parameter to ICPMP optimizer
   - Reads from `monthlyHourLimits[]` configuration

2. **config_optimizer_v3.py**:
   - Added `monthly_ot_cap` parameter to `calculate_optimal_with_u_slots()`
   - Replaced hard-coded `72.0` with parameter (lines 221, 254)
   - Added OT-aware capacity for Scheme A/B (new feature)

3. **Test Coverage**:
   - `test_scheme_a_apo_124h_ot.py` verifies correct behavior
   - 72h OT → 18 employees, 124h OT → 17 employees ✓

## Deployment Steps

### 1. Push Changes to GitHub
```bash
cd /Users/glori/1\ Anthony_Workspace/My\ Developments/NGRS/ngrs-solver-v0.7/ngrssolver
git push origin main
```

### 2. Deploy to Production Server
```bash
# SSH into EC2
ssh ubuntu@ec2-47-130-131-6.ap-southeast-1.compute.amazonaws.com

# Navigate to deployment directory
cd /opt/ngrs-solver

# Pull latest changes
git pull origin main

# Restart service
sudo systemctl restart ngrs-solver

# Verify service is running
sudo systemctl status ngrs-solver

# Check logs for any errors
sudo journalctl -u ngrs-solver -f
```

### 3. Verify Deployment
```bash
# Health check
curl https://ngrssolver09.comcentricapps.com/health

# Test with a small input
curl -X POST https://ngrssolver09.comcentricapps.com/solve \
  -H "Content-Type: application/json" \
  -d @input/test_scheme_p_fix.json
```

### 4. Test with Production Input
Submit RST-20251228-B6F519CB or similar Scheme A + APO input:
```bash
# Using async endpoint
curl -X POST https://ngrssolver09.comcentricapps.com/solve/async \
  -H "Content-Type: application/json" \
  -d @RST-20251228-B6F519CB.json

# Poll for result
curl https://ngrssolver09.comcentricapps.com/solve/async/{job_id}
```

**Expected Outcome**:
- ICPMP selects 14-17 employees (not 21)
- Status: OPTIMAL (not INFEASIBLE)
- All 310 slots assigned
- OT capacity log shows "124h" for Scheme A + APO

## Validation Checklist
- [ ] Code pushed to GitHub
- [ ] Production server pulls latest code  
- [ ] Service restarts without errors
- [ ] Health endpoint responds 200 OK
- [ ] Small test input processes successfully
- [ ] ICPMP logs show scheme-specific OT capacity (check for "Monthly OT cap for A + APO: 124h")
- [ ] Scheme A + APO inputs select correct employee count (~14-17 vs previous 21)
- [ ] Result status is OPTIMAL (not INFEASIBLE)

## Rollback Plan
If issues occur:
```bash
ssh ubuntu@ec2-47-130-131-6.ap-southeast-1.compute.amazonaws.com
cd /opt/ngrs-solver
git log --oneline -5                    # View recent commits
git revert HEAD                         # Revert to previous version
# OR
git reset --hard d418eb8                # Reset to known good commit
sudo systemctl restart ngrs-solver
```

## Monitoring
Watch logs during initial production use:
```bash
sudo journalctl -u ngrs-solver -f | grep -i "monthly ot\|icpmp\|capacity adjustment"
```

Look for:
- ✅ "Monthly OT cap for A + APO: 124h" (scheme-specific limits detected)
- ✅ "OT-aware capacity adjustment (monthly cap: 124.0h)" (correct value used)
- ✅ "employeesRequired: 14-17" in ICPMP metadata (vs previous 21)
- ❌ Any Python exceptions or TypeError

## Questions?
Contact: Anthony (user who reported the issue)
Documentation: See [CONSTRAINT_ARCHITECTURE.md](implementation_docs/CONSTRAINT_ARCHITECTURE.md)
