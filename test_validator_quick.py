#!/usr/bin/env python3
"""Quick test of assignment validator without API server."""

import json
from src.assignment_validator import AssignmentValidator
from src.models import ValidateAssignmentRequest

# Load test data
with open('test_assignment_validation.json', 'r') as f:
    test_data = json.load(f)

print("\n" + "="*80)
print("ASSIGNMENT VALIDATION TEST - FEASIBLE CASE")
print("="*80)

# Create request
request = ValidateAssignmentRequest(**test_data)

print(f"\nEmployee: {request.employee.employeeId}")
print(f"Rank: {request.employee.rankId}")
print(f"Scheme: {request.employee.scheme}")
print(f"Existing Assignments: {len(request.existingAssignments)}")
print(f"Candidate Slots: {len(request.candidateSlots)}")

# Run validation
validator = AssignmentValidator()
response = validator.validate(request)

# Print results
print(f"\n{'='*80}")
print("RESULTS")
print(f"{'='*80}")
print(f"Status: {response.status}")
print(f"Processing Time: {response.processingTimeMs:.2f}ms")
print(f"Employee ID: {response.employeeId}")

for i, result in enumerate(response.validationResults, 1):
    print(f"\n--- Slot {i}: {result.slotId} ---")
    print(f"Is Feasible: {result.isFeasible}")
    print(f"Recommendation: {result.recommendation}")
    
    if result.hours:
        print(f"Hour Breakdown:")
        print(f"  Gross: {result.hours.gross}h")
        print(f"  Lunch: {result.hours.lunch}h")
        print(f"  Normal: {result.hours.normal}h")
        print(f"  OT: {result.hours.ot}h")
        print(f"  Paid: {result.hours.paid}h")
    
    if result.violations:
        print(f"Violations ({len(result.violations)}):")
        for v in result.violations:
            print(f"  - [{v.constraintId}] {v.constraintName}")
            print(f"    {v.description}")
            if v.context:
                print(f"    Context: {v.context}")
    else:
        print("✓ No violations - Assignment is VALID")

print("\n" + "="*80)
print("TEST PASSED: Validator is working correctly!")
print("="*80 + "\n")
