#!/usr/bin/env python3
"""Generate sample output JSON for validation endpoint."""

import json
from src.assignment_validator import AssignmentValidator
from src.models import ValidateAssignmentRequest

# Load test data
with open('test_assignment_validation.json', 'r') as f:
    test_data = json.load(f)

# Create request and validate
request = ValidateAssignmentRequest(**test_data)
validator = AssignmentValidator()
response = validator.validate(request)

# Convert to dict for JSON output
output = {
    'status': response.status,
    'validationResults': [
        {
            'slotId': r.slotId,
            'isFeasible': r.isFeasible,
            'violations': [
                {
                    'constraintId': v.constraintId,
                    'constraintName': v.constraintName,
                    'violationType': v.violationType,
                    'description': v.description,
                    'context': v.context
                } for v in r.violations
            ],
            'recommendation': r.recommendation
        } for r in response.validationResults
    ],
    'employeeId': response.employeeId,
    'timestamp': response.timestamp,
    'processingTimeMs': response.processingTimeMs
}

# Save to file
with open('test_assignment_validation_output.json', 'w') as f:
    json.dump(output, f, indent=2)

print('Output saved to: test_assignment_validation_output.json')
print(json.dumps(output, indent=2))
