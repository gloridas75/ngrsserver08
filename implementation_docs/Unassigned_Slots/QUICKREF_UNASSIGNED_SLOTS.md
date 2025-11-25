# 🚀 Quick Reference - Unassigned Slots Feature

**Version**: 0.7.0 | **Date**: November 15, 2025 | **Status**: ✅ Implemented

---

## 📋 What Changed

### Before (v0.6)
```python
# Solver could return INFEASIBLE
model.Add(sum(assignments) == headcount)
model.Maximize(sum(assignments))
```

### After (v0.7)
```python
# Solver always returns OPTIMAL with explicit unassigned
model.Add(sum(assignments) + unassigned == headcount)
model.Minimize(1_000_000 * total_unassigned)
```

---

## 🎯 Key Features

| Feature | Description | Benefit |
|---------|-------------|---------|
| **Unassigned Variables** | Boolean var per slot | Explicit gaps identified |
| **Modified Constraints** | `+ unassigned` in headcount | Always feasible solution |
| **Priority Objective** | Minimize unassigned first | Max slot coverage |
| **Enhanced Output** | Status field + reason | Clear visibility |
| **Strict Constraints** | All hard rules enforced | No violations |

---

## 📍 Code Locations

| Component | File | Line | What |
|-----------|------|------|------|
| Variables | solver_engine.py | ~70 | `unassigned = {}` |
| Aggregation | solver_engine.py | ~108 | `total_unassigned` |
| Constraints | solver_engine.py | ~78 | `+ unassigned[slot_id]` |
| Objective | solver_engine.py | ~120 | `Minimize(BIG * total)` |
| Extraction | solver_engine.py | ~160 | ASSIGNED/UNASSIGNED |
| Validation | solver_engine.py | ~280 | `assigned_slots` filter |
| Breakdown | solver_engine.py | ~520 | `unassignedSlots{}` |

---

## 📤 Output Format

```json
{
  "assignments": [
    {"status": "ASSIGNED", "employeeId": "EMP123", ...},
    {"status": "UNASSIGNED", "employeeId": null, "reason": "...", ...}
  ],
  "scoreBreakdown": {
    "unassignedSlots": {
      "count": 3,
      "percentage": 15.0,
      "slots": [...]
    }
  }
}
```

---

## ✅ Verification

- [x] No `== headcount` without `+ unassigned`
- [x] Objective uses `Minimize(BIG * total_unassigned)`
- [x] Output includes both ASSIGNED and UNASSIGNED
- [x] All constraints check `assigned_slots` only
- [x] Context stores `unassigned` and `total_unassigned`

---

## 🧪 Quick Test

```bash
cd ngrssolver
python src/run_solver.py --in input/test.json --out output/test.json
cat output/test.json | jq '.scoreBreakdown.unassignedSlots'
```

---

## 📖 Documentation

- **Complete Guide**: `CHANGES_UNASSIGNED_SLOTS.md`
- **Code Diff**: `DIFF_UNASSIGNED_SLOTS.md`
- **Verification**: `VERIFICATION_UNASSIGNED_SLOTS.md`
- **Summary**: `SUMMARY_UNASSIGNED_SLOTS.md`

---

## 🎓 Key Concepts

**Unassigned Slot**: Slot that can't be filled without violating hard constraints

**BIG Multiplier**: 1,000,000 weight to prioritize slot filling

**Status Field**: "ASSIGNED" or "UNASSIGNED" in output

**Hard Constraints**: Still strict - no violations allowed

---

## ⚡ Quick Facts

- **1 file modified**: `context/engine/solver_engine.py`
- **~110 lines changed**: Added functionality
- **3 new variables**: `unassigned`, `total_unassigned`, `BIG_MULTIPLIER`
- **0 constraints weakened**: All remain strict
- **100% backward compatible**: Existing assignments unchanged

---

**Status**: ✅ Ready for Testing | **Next**: Run test suite
