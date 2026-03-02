#!/usr/bin/env python3
"""Test normalization with edge case: missing maxOvertimeHours."""
from context.engine.data_loader import normalize_monthly_hour_limits

# Test case: monthlyHourLimits without standardMonthlyHours reference
test_data = {
    'monthlyHourLimits': [
        {
            'id': 'custom_limit',
            'description': 'Custom limit without maxOvertimeHours',
            'valuesByMonthLength': {
                '30': {
                    'minimumContractualHours': 189
                    # Missing maxOvertimeHours
                },
                '31': {
                    'minimumContractualHours': 195,
                    'maxOvertimeHours': 60  # Has it, should not be changed
                }
            }
        }
    ]
}

print("Before normalization:")
month_30_val = test_data['monthlyHourLimits'][0]['valuesByMonthLength']['30'].get('maxOvertimeHours', 'MISSING')
month_31_val = test_data['monthlyHourLimits'][0]['valuesByMonthLength']['31'].get('maxOvertimeHours', 'MISSING')
print(f"  Month 30: maxOvertimeHours = {month_30_val}")
print(f"  Month 31: maxOvertimeHours = {month_31_val}")

result = normalize_monthly_hour_limits(test_data)

print("\nAfter normalization:")
month_30_after = result['monthlyHourLimits'][0]['valuesByMonthLength']['30']['maxOvertimeHours']
month_31_after = result['monthlyHourLimits'][0]['valuesByMonthLength']['31']['maxOvertimeHours']
print(f"  Month 30: maxOvertimeHours = {month_30_after} (should be 72 - default)")
print(f"  Month 31: maxOvertimeHours = {month_31_after} (should be 60 - unchanged)")
