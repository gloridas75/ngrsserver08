# Auto-Optimization Configuration Guide

## Overview

The auto-optimization feature tests multiple `strictAdherenceRatio` values to find the optimal balance that minimizes employees while achieving 100% coverage.

## Performance Considerations

### Problem Scale
- **Small (≤100 employees, ≤500 slots)**: Can test 11 ratios (~1-2 minutes)
- **Medium (100-300 employees, 500-1500 slots)**: Reduce to 5-7 ratios (~5-10 minutes)
- **Large (300-500 employees, 1500+ slots)**: Use 3-5 ratios or manual override (~10-30 minutes)

### Time Impact
```
CP-SAT runs = number_of_ratios × time_per_run
Example: 11 ratios × 60s = 11 minutes max
```

## Configuration Options

### Global Configuration (Recommended for most cases)

```json
{
  "solverConfig": {
    "autoOptimizeStrictRatio": true,
    "minStrictRatio": 0.5,     // Start at 50% strict
    "maxStrictRatio": 0.8,     // End at 80% strict
    "strictRatioStep": 0.1     // Test every 10%
  }
}
```

**Result**: Tests 4 ratios: 50%, 60%, 70%, 80%

### Faster Configuration (For large workforces)

```json
{
  "solverConfig": {
    "autoOptimizeStrictRatio": true,
    "minStrictRatio": 0.6,     // Narrow range
    "maxStrictRatio": 0.75,    // Based on experience
    "strictRatioStep": 0.05    // Finer steps
  }
}
```

**Result**: Tests 4 ratios: 60%, 65%, 70%, 75%

### Manual Override (Skip optimization)

```json
{
  "solverConfig": {
    "autoOptimizeStrictRatio": false,
    "strictAdherenceRatio": 0.7  // Fixed 70% strict
  }
}
```

**Result**: Single CP-SAT run with 70% strict adherence

## Per-Requirement Configuration (Future Enhancement)

### Option 1: Per-Demand Override

```json
{
  "demandItems": [
    {
      "demandId": "DI-001",
      "requirements": [
        {
          "requirementId": "REQ-001",
          "headcount": 5,
          "workPattern": ["D","D","D","D","O","O","D","D","D","D","D","O"],
          "optimizationConfig": {
            "autoOptimizeStrictRatio": true,
            "minStrictRatio": 0.65,
            "maxStrictRatio": 0.8,
            "strictRatioStep": 0.05
          }
        }
      ]
    }
  ]
}
```

**Benefit**: Different patterns may favor different ratios
- 12-day pattern: 60-75% works well
- 6-day pattern: 70-80% may be optimal
- Complex patterns: Test wider range

### Option 2: Pattern-Based Defaults

The system could auto-suggest ranges based on pattern characteristics:

```python
# Pseudo-code for smart defaults
if pattern_has_long_work_stretches(workPattern):
    suggested_range = (0.65, 0.8)  # More strict works better
elif pattern_is_balanced(workPattern):
    suggested_range = (0.5, 0.75)  # Moderate approach
else:
    suggested_range = (0.4, 0.7)   # Need more flexibility
```

## Recommended Strategies

### Strategy 1: Quick Test First
1. Run with **manual ratio 0.7** (70% strict)
2. If OPTIMAL → Done (save time!)
3. If INFEASIBLE → Enable auto-optimization with narrow range

### Strategy 2: Learn from History
1. Track optimal ratios from past runs
2. Use those as defaults for similar patterns
3. Narrow the test range around historical optimum

### Strategy 3: Tiered Approach
```json
{
  "solverConfig": {
    "autoOptimizeStrictRatio": true,
    "minStrictRatio": 0.6,
    "maxStrictRatio": 0.8,
    "strictRatioStep": 0.2,      // First: coarse steps (60%, 80%)
    "refinementStep": 0.05        // Then: refine around best (65%, 70%, 75%)
  }
}
```

**Result**: 
- Phase 1: Test 60%, 80% (2 runs)
- Phase 2: If 60% optimal, test 55%, 65% (2 runs)
- Total: 4 runs instead of 11

## Time Savings Comparison

| Employees | Slots | 11 Ratios | 5 Ratios | Manual | Savings |
|-----------|-------|-----------|----------|--------|---------|
| 50        | 155   | ~11 min   | ~5 min   | ~1 min | 82-91%  |
| 100       | 500   | ~30 min   | ~14 min  | ~3 min | 90%     |
| 300       | 1500  | ~90 min   | ~40 min  | ~8 min | 91%     |
| 500       | 2500  | ~150 min  | ~65 min  | ~15 min| 90%     |

## Best Practices

### For Production Use:
1. **First run**: Use auto-optimization to find optimal ratio
2. **Save result**: Store `selectedStrictRatio` in database
3. **Subsequent runs**: Use saved ratio (manual mode)
4. **Re-optimize**: Only when pattern/workforce changes significantly

### For Testing:
1. Use narrow ranges (3-5 ratios)
2. Lower time limits (--time 30 or 60)
3. Early stopping if OPTIMAL found quickly

### For API/Real-time:
1. Default to manual mode with learned ratio (e.g., 0.7)
2. Offer auto-optimization as async job
3. Cache results per pattern type

## Configuration Examples

### Minimal Testing (3 ratios)
```json
{
  "solverConfig": {
    "autoOptimizeStrictRatio": true,
    "minStrictRatio": 0.6,
    "maxStrictRatio": 0.8,
    "strictRatioStep": 0.1
  }
}
```
Tests: 60%, 70%, 80%

### Balanced Testing (5 ratios)
```json
{
  "solverConfig": {
    "autoOptimizeStrictRatio": true,
    "minStrictRatio": 0.5,
    "maxStrictRatio": 0.8,
    "strictRatioStep": 0.075
  }
}
```
Tests: 50%, 57.5%, 65%, 72.5%, 80%

### Comprehensive Testing (11 ratios) - Default
```json
{
  "solverConfig": {
    "autoOptimizeStrictRatio": true
    // Uses defaults: 50-80%, step 0.05
  }
}
```
Tests: 50%, 55%, 60%, 65%, 70%, 75%, 80%

## Implementation Roadmap

### Phase 1: ✅ Current (Global config)
- Global auto-optimization enabled
- Configurable min/max/step
- Select minimum employee solution

### Phase 2: 🔄 Per-Requirement Config (Recommended)
- Move optimization config to requirement level
- Different patterns → different optimal ratios
- Parallel optimization for multiple requirements

### Phase 3: 🔮 Smart Optimization
- Machine learning to predict optimal ratio
- Pattern analysis for automatic range selection
- Early stopping when optimal found
- Cached results for similar patterns

## Conclusion

**For 500 employees**: 
- ✅ Use 3-5 ratios (saves 50-70% time)
- ✅ Consider per-requirement config (parallel optimization)
- ✅ Cache and reuse optimal ratios
- ❌ Don't use default 11 ratios in production

The per-requirement approach is **highly recommended** for large-scale deployments!
