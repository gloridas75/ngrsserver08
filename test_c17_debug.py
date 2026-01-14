#!/usr/bin/env python3
import json
from src.assignment_validator import AssignmentValidator
from src.models import ValidateAssignmentRequest

test_c17 = {
    'employee': {
        'employeeId': '00011111',
        'gender': 'M',
        'rankId': 'SO',
        'productTypeId': 'APO',
        'scheme': 'Scheme A',
        'workPattern': ['D','D','D','D','D','D','O'],
        'normalHours': 44.0,
        'otHours': 80.0
    },
    'existingAssignments': [
        {
            'assignmentId': f'A{i}',
            'date': f'2026-02-{i:02d}',
            'slotId': f'S{i}',
            'shiftCode': 'D',
            'startDateTime': f'2026-02-{i:02d}T08:00:00',
            'endDateTime': f'2026-02-{i:02d}T20:00:00',
            'hours': {'gross': 12.0, 'lunch': 1.0, 'normal': 8.8, 'ot': 2.2, 'restDayPay': 0.0, 'paid': 12.0}
        }
        for i in range(2, 26)  # 24 existing assignments
    ],
    'candidateSlots': [
        {
            'slotId': 'S26',
            'startDateTime': '2026-02-26T08:00:00',
            'endDateTime': '2026-02-26T20:00:00',
            'shiftCode': 'D'
        }
    ]
}

validator = AssignmentValidator()
request = ValidateAssignmentRequest(**test_c17)
response = validator.validate(request)

print('Test C17: APGD-D10 Monthly OT')
print('='*60)
print('Feb 2026: 28 days × 3.8h = 106.4h OT cap')
print('Existing: 24 assignments × 2.2h OT = 52.8h')
print('Candidate: 1 assignment × 2.2h OT')
print('Total: 55.0h OT')
print()
print('Result:', 'FEASIBLE' if response.validationResults[0].isFeasible else 'NOT FEASIBLE')

if not response.validationResults[0].isFeasible:
    for v in response.validationResults[0].violations:
        print(f'\n{v.constraintId}: {v.description}')
        if v.context:
            print(f'Context: {v.context}')
else:
    print('✓ Correctly allows 55.0h OT (under 106.4h APGD-D10 cap)')
