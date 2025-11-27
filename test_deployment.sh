#!/bin/bash
echo "Testing production deployment..."
curl -X POST https://ngrssolver08.comcentricapps.com/solve/incremental \
  -H "Content-Type: application/json" \
  -d @input/incremental/test_feasible_5joiners.json \
  -o output/test_feasible_5joiners_auto_offset.json \
  --silent --show-error --max-time 600

if [ $? -eq 0 ]; then
    echo "✓ Solve completed"
    python3 << 'PYTHON'
import json
with open('output/test_feasible_5joiners_auto_offset.json') as f:
    result = json.load(f)
    
print(f"\nSolver Status: {result.get('status', 'UNKNOWN')}")
print(f"Solve Time: {result.get('solveTime', {}).get('durationSeconds', 0):.3f}s")

# Check for optimized offsets
if 'optimizedRotationOffsets' in result:
    print(f"\n✓ Optimized Offsets Found:")
    for emp_id, offset in sorted(result['optimizedRotationOffsets'].items()):
        print(f"  {emp_id}: offset={offset}")
else:
    print("\n✗ No optimized offsets in output")

# Check coverage
solve_window = [a for a in result['assignments'] if a['date'] >= '2025-12-20' and a['date'] <= '2025-12-31']
assigned = sum(1 for a in solve_window if a.get('employeeId') is not None)

print(f"\nCoverage: {assigned}/{len(solve_window)} slots ({assigned/len(solve_window)*100:.1f}%)")
PYTHON
else
    echo "✗ Deployment test failed"
fi
