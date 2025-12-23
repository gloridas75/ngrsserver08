"""Test suite for constraint configuration v0.98

Tests the new constraint JSON format and helper functions.
"""

import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from context.engine.constraint_config import (
    get_constraint_param,
    get_scheme_specific_value,
    get_constraint_by_id,
    is_constraint_enabled,
    _matches_filters
)


class TestConstraintConfigNewFormat:
    """Test NEW format (v0.98) constraint parsing"""
    
    def test_simple_default_value(self):
        """Test simple defaultValue without employee"""
        ctx = {
            'constraintList': [
                {
                    'id': 'momWeeklyHoursCap44h',
                    'defaultValue': 44
                }
            ]
        }
        
        value = get_constraint_param(ctx, 'momWeeklyHoursCap44h', default=40)
        assert value == 44
    
    def test_scheme_override_simple(self):
        """Test simple scheme override (just a number)"""
        ctx = {
            'constraintList': [
                {
                    'id': 'momDailyHoursCap',
                    'defaultValue': 9,
                    'schemeOverrides': {
                        'A': 14,
                        'B': 13,
                        'P': 9
                    }
                }
            ]
        }
        
        emp_a = {'employeeId': 'E001', 'scheme': 'A', 'productTypes': []}
        emp_b = {'employeeId': 'E002', 'scheme': 'B', 'productTypes': []}
        emp_p = {'employeeId': 'E003', 'scheme': 'P', 'productTypes': []}
        
        assert get_constraint_param(ctx, 'momDailyHoursCap', emp_a) == 14
        assert get_constraint_param(ctx, 'momDailyHoursCap', emp_b) == 13
        assert get_constraint_param(ctx, 'momDailyHoursCap', emp_p) == 9
    
    def test_scheme_override_with_product_type_filter(self):
        """Test complex scheme override with productTypes filter"""
        ctx = {
            'constraintList': [
                {
                    'id': 'maxConsecutiveWorkingDays',
                    'defaultValue': 12,
                    'schemeOverrides': {
                        'A': {
                            'productTypes': ['APO'],
                            'value': 8
                        }
                    }
                }
            ]
        }
        
        emp_apgd = {'employeeId': 'E001', 'scheme': 'A', 'productTypes': ['APO']}
        emp_standard = {'employeeId': 'E002', 'scheme': 'A', 'productTypes': ['Standard']}
        emp_b = {'employeeId': 'E003', 'scheme': 'B', 'productTypes': []}
        
        # APGD-D10 (A + APO) gets 8
        assert get_constraint_param(ctx, 'maxConsecutiveWorkingDays', emp_apgd) == 8
        
        # Standard Scheme A gets default (no productTypes match)
        assert get_constraint_param(ctx, 'maxConsecutiveWorkingDays', emp_standard) == 12
        
        # Scheme B gets default
        assert get_constraint_param(ctx, 'maxConsecutiveWorkingDays', emp_b) == 12
    
    def test_scheme_override_rest_period_scheme_p(self):
        """Test Scheme P with 1 hour rest (critical test)"""
        ctx = {
            'constraintList': [
                {
                    'id': 'apgdMinRestBetweenShifts',
                    'defaultValue': 8,
                    'schemeOverrides': {
                        'P': 1
                    }
                }
            ]
        }
        
        emp_p = {'employeeId': 'E001', 'scheme': 'P', 'productTypes': []}
        emp_a = {'employeeId': 'E002', 'scheme': 'A', 'productTypes': []}
        
        assert get_constraint_param(ctx, 'apgdMinRestBetweenShifts', emp_p) == 1
        assert get_constraint_param(ctx, 'apgdMinRestBetweenShifts', emp_a) == 8
    
    def test_scheme_normalization(self):
        """Test that 'Scheme A' is normalized to 'A'"""
        ctx = {
            'constraintList': [
                {
                    'id': 'momDailyHoursCap',
                    'defaultValue': 9,
                    'schemeOverrides': {
                        'A': 14
                    }
                }
            ]
        }
        
        # Test various scheme formats
        emp1 = {'employeeId': 'E001', 'scheme': 'A', 'productTypes': []}
        emp2 = {'employeeId': 'E002', 'scheme': 'Scheme A', 'productTypes': []}
        emp3 = {'employeeId': 'E003', 'scheme': 'SCHEME_A', 'productTypes': []}
        
        assert get_constraint_param(ctx, 'momDailyHoursCap', emp1) == 14
        assert get_constraint_param(ctx, 'momDailyHoursCap', emp2) == 14
        assert get_constraint_param(ctx, 'momDailyHoursCap', emp3) == 14


class TestConstraintConfigOldFormat:
    """Test OLD format (v0.7) constraint parsing for backward compatibility"""
    
    def test_old_format_scheme_specific(self):
        """Test OLD format with scheme-specific params"""
        ctx = {
            'constraintList': [
                {
                    'id': 'momDailyHoursCap',
                    'params': {
                        'maxDailyHoursA': 14,
                        'maxDailyHoursB': 13,
                        'maxDailyHoursP': 9
                    }
                }
            ]
        }
        
        emp_a = {'employeeId': 'E001', 'scheme': 'A', 'productTypes': []}
        emp_b = {'employeeId': 'E002', 'scheme': 'B', 'productTypes': []}
        
        value_a = get_constraint_param(ctx, 'momDailyHoursCap', emp_a, 
                                      param_name='maxDailyHours', default=9)
        value_b = get_constraint_param(ctx, 'momDailyHoursCap', emp_b,
                                      param_name='maxDailyHours', default=9)
        
        assert value_a == 14
        assert value_b == 13
    
    def test_old_format_with_general(self):
        """Test OLD format with General fallback"""
        ctx = {
            'constraintList': [
                {
                    'id': 'testConstraint',
                    'params': {
                        'maxValueGeneral': 10,
                        'maxValueA': 20
                    }
                }
            ]
        }
        
        emp_a = {'employeeId': 'E001', 'scheme': 'A', 'productTypes': []}
        emp_b = {'employeeId': 'E002', 'scheme': 'B', 'productTypes': []}
        
        assert get_constraint_param(ctx, 'testConstraint', emp_a, 
                                   param_name='maxValue', default=5) == 20
        assert get_constraint_param(ctx, 'testConstraint', emp_b,
                                   param_name='maxValue', default=5) == 10


class TestFilterMatching:
    """Test filter matching logic"""
    
    def test_product_type_filter_match(self):
        """Test productTypes filter matching"""
        rule = {'productTypes': ['APO'], 'value': 8}
        
        assert _matches_filters(rule, ['APO'], '') == True
        assert _matches_filters(rule, ['APO', 'Standard'], '') == True  # Has APO
        assert _matches_filters(rule, ['Standard'], '') == False
        assert _matches_filters(rule, [], '') == False
    
    def test_rank_filter_match(self):
        """Test ranks filter matching"""
        rule = {'ranks': ['SO', 'SSO'], 'value': 10}
        
        assert _matches_filters(rule, [], 'SO') == True
        assert _matches_filters(rule, [], 'SSO') == True
        assert _matches_filters(rule, [], 'SGT') == False
        assert _matches_filters(rule, [], '') == False
    
    def test_combined_filters(self):
        """Test multiple filters (productTypes AND ranks)"""
        rule = {'productTypes': ['APO'], 'ranks': ['SO'], 'value': 8}
        
        assert _matches_filters(rule, ['APO'], 'SO') == True
        assert _matches_filters(rule, ['APO'], 'SGT') == False  # rank doesn't match
        assert _matches_filters(rule, ['Standard'], 'SO') == False  # productType doesn't match
        assert _matches_filters(rule, ['Standard'], 'SGT') == False  # neither match


class TestHelperFunctions:
    """Test helper utility functions"""
    
    def test_get_constraint_by_id(self):
        """Test finding constraint by ID"""
        ctx = {
            'constraintList': [
                {'id': 'constraint1', 'defaultValue': 10},
                {'id': 'constraint2', 'defaultValue': 20}
            ]
        }
        
        c1 = get_constraint_by_id(ctx, 'constraint1')
        c2 = get_constraint_by_id(ctx, 'constraint2')
        c_missing = get_constraint_by_id(ctx, 'constraint3')
        
        assert c1['defaultValue'] == 10
        assert c2['defaultValue'] == 20
        assert c_missing is None
    
    def test_is_constraint_enabled(self):
        """Test constraint enabled check"""
        ctx = {
            'constraintList': [
                {'id': 'enabled1', 'defaultValue': 10},
                {'id': 'disabled1', 'defaultValue': 20, 'enabled': False}
            ]
        }
        
        assert is_constraint_enabled(ctx, 'enabled1') == True
        assert is_constraint_enabled(ctx, 'disabled1') == False
        assert is_constraint_enabled(ctx, 'missing') == False
    
    def test_get_scheme_specific_value(self):
        """Test convenience wrapper function"""
        ctx = {
            'constraintList': [
                {
                    'id': 'momDailyHoursCap',
                    'defaultValue': 9,
                    'schemeOverrides': {'A': 14}
                }
            ]
        }
        
        emp = {'employeeId': 'E001', 'scheme': 'A', 'productTypes': []}
        value = get_scheme_specific_value(ctx, 'momDailyHoursCap', emp, default=9)
        
        assert value == 14


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_missing_constraint(self):
        """Test behavior when constraint ID not found"""
        ctx = {'constraintList': []}
        
        value = get_constraint_param(ctx, 'nonexistent', default=99)
        assert value == 99
    
    def test_empty_constraint_list(self):
        """Test with empty constraintList"""
        ctx = {'constraintList': []}
        
        emp = {'employeeId': 'E001', 'scheme': 'A', 'productTypes': []}
        value = get_constraint_param(ctx, 'anyConstraint', emp, default=42)
        
        assert value == 42
    
    def test_no_constraint_list(self):
        """Test with missing constraintList key"""
        ctx = {}
        
        value = get_constraint_param(ctx, 'anyConstraint', default=100)
        assert value == 100
    
    def test_employee_without_scheme(self):
        """Test employee dict without scheme field"""
        ctx = {
            'constraintList': [
                {
                    'id': 'test',
                    'defaultValue': 10,
                    'schemeOverrides': {'A': 20}
                }
            ]
        }
        
        emp = {'employeeId': 'E001', 'productTypes': []}  # No 'scheme' field
        value = get_constraint_param(ctx, 'test', emp)
        
        # Should default to 'A' scheme
        assert value == 20


class TestMonthlyHourLimits:
    """Test monthly hour limits configuration"""
    
    def test_get_employee_type_local(self):
        """Test employee type detection for local employee"""
        from context.engine.constraint_config import get_employee_type
        
        emp_local = {'employeeId': 'E001', 'local': 1}
        assert get_employee_type(emp_local) == 'Local'
    
    def test_get_employee_type_foreigner(self):
        """Test employee type detection for foreigner employee"""
        from context.engine.constraint_config import get_employee_type
        
        emp_foreigner = {'employeeId': 'E002', 'local': 0}
        assert get_employee_type(emp_foreigner) == 'Foreigner'
    
    def test_standard_monthly_limits_feb(self):
        """Test standard monthly limits for February (28 days)"""
        from context.engine.constraint_config import get_monthly_hour_limits
        
        ctx = {
            'monthlyHourLimits': [
                {
                    'id': 'standardMonthlyHours',
                    'applicableTo': {'employeeType': 'All', 'schemes': 'All'},
                    'valuesByMonthLength': {
                        '28': {'normalHours': 176, 'maxOvertimeHours': 112, 'totalMaxHours': 288}
                    }
                }
            ]
        }
        
        emp = {'employeeId': 'E001', 'local': 1, 'scheme': 'B', 'productTypes': []}
        limits = get_monthly_hour_limits(ctx, emp, 2025, 2)  # Feb 2025 = 28 days
        
        assert limits['normalHours'] == 176
        assert limits['maxOvertimeHours'] == 112
        assert limits['totalMaxHours'] == 288
        assert limits['minimumContractualHours'] is None
        assert limits['monthDays'] == 28
    
    def test_apgd_minimum_local_excluding_cpl_sgt(self):
        """Test APGD-D10 minimum hours for Local employee (non CPL/SGT)"""
        from context.engine.constraint_config import get_monthly_hour_limits
        
        ctx = {
            'monthlyHourLimits': [
                {
                    'id': 'apgdMinimumContractualHours',
                    'enforcement': 'soft',
                    'applicableTo': {
                        'employeeType': ['Local', 'Foreigner'],
                        'schemes': ['A'],
                        'productTypes': ['APO'],
                        'ranksExcluded': {'Foreigner': ['CPL', 'SGT']}
                    },
                    'valuesByMonthLength': {
                        '28': {'minimumContractualHours': 224, 'maxOvertimeHours': 112, 'totalMaxHours': 288}
                    }
                }
            ]
        }
        
        emp_local = {'employeeId': 'E001', 'local': 1, 'scheme': 'A', 'productTypes': ['APO'], 'rank': 'SO'}
        limits = get_monthly_hour_limits(ctx, emp_local, 2025, 2)
        
        assert limits['minimumContractualHours'] == 224
        assert limits['maxOvertimeHours'] == 112
        assert limits['enforcement'] == 'soft'
        assert limits['ruleId'] == 'apgdMinimumContractualHours'
    
    def test_apgd_foreigner_cpl_sgt_higher_minimum(self):
        """Test APGD-D10 higher minimum for Foreigner CPL/SGT"""
        from context.engine.constraint_config import get_monthly_hour_limits
        
        ctx = {
            'monthlyHourLimits': [
                {
                    'id': 'apgdMinimumContractualHoursCplSgt',
                    'enforcement': 'soft',
                    'applicableTo': {
                        'employeeType': ['Foreigner'],
                        'schemes': ['A'],
                        'productTypes': ['APO'],
                        'ranks': ['CPL', 'SGT']
                    },
                    'valuesByMonthLength': {
                        '28': {'minimumContractualHours': 244, 'maxOvertimeHours': 112, 'totalMaxHours': 288}
                    }
                }
            ]
        }
        
        emp_cpl = {'employeeId': 'E002', 'local': 0, 'scheme': 'A', 'productTypes': ['APO'], 'rank': 'CPL'}
        limits = get_monthly_hour_limits(ctx, emp_cpl, 2025, 2)
        
        assert limits['minimumContractualHours'] == 244
        assert limits['enforcement'] == 'soft'
    
    def test_apgd_foreigner_non_cpl_sgt_gets_lower_minimum(self):
        """Test APGD-D10 Foreigner non-CPL/SGT gets 224h not 244h"""
        from context.engine.constraint_config import get_monthly_hour_limits
        
        ctx = {
            'monthlyHourLimits': [
                {
                    'id': 'apgdMinimumContractualHours',
                    'enforcement': 'soft',
                    'applicableTo': {
                        'employeeType': ['Local', 'Foreigner'],
                        'schemes': ['A'],
                        'productTypes': ['APO'],
                        'ranksExcluded': {'Foreigner': ['CPL', 'SGT']}
                    },
                    'valuesByMonthLength': {
                        '28': {'minimumContractualHours': 224, 'maxOvertimeHours': 112}
                    }
                },
                {
                    'id': 'apgdMinimumContractualHoursCplSgt',
                    'enforcement': 'soft',
                    'applicableTo': {
                        'employeeType': ['Foreigner'],
                        'schemes': ['A'],
                        'productTypes': ['APO'],
                        'ranks': ['CPL', 'SGT']
                    },
                    'valuesByMonthLength': {
                        '28': {'minimumContractualHours': 244, 'maxOvertimeHours': 112}
                    }
                }
            ]
        }
        
        # Foreigner with rank SO (not CPL/SGT) should get 224h
        emp_so = {'employeeId': 'E003', 'local': 0, 'scheme': 'A', 'productTypes': ['APO'], 'rank': 'SO'}
        limits = get_monthly_hour_limits(ctx, emp_so, 2025, 2)
        
        assert limits['minimumContractualHours'] == 224  # Not 244!
    
    def test_different_month_lengths(self):
        """Test different month lengths return correct values"""
        from context.engine.constraint_config import get_monthly_hour_limits
        
        ctx = {
            'monthlyHourLimits': [
                {
                    'id': 'standardMonthlyHours',
                    'applicableTo': {'employeeType': 'All', 'schemes': 'All'},
                    'valuesByMonthLength': {
                        '28': {'normalHours': 176, 'maxOvertimeHours': 112},
                        '29': {'normalHours': 182, 'maxOvertimeHours': 116},
                        '30': {'normalHours': 189, 'maxOvertimeHours': 120},
                        '31': {'normalHours': 195, 'maxOvertimeHours': 124}
                    }
                }
            ]
        }
        
        emp = {'employeeId': 'E001', 'local': 1, 'scheme': 'B', 'productTypes': []}
        
        # Feb 2025 (28 days)
        limits_feb = get_monthly_hour_limits(ctx, emp, 2025, 2)
        assert limits_feb['normalHours'] == 176
        assert limits_feb['maxOvertimeHours'] == 112
        
        # April 2025 (30 days)
        limits_apr = get_monthly_hour_limits(ctx, emp, 2025, 4)
        assert limits_apr['normalHours'] == 189
        assert limits_apr['maxOvertimeHours'] == 120
        
        # May 2025 (31 days)
        limits_may = get_monthly_hour_limits(ctx, emp, 2025, 5)
        assert limits_may['normalHours'] == 195
        assert limits_may['maxOvertimeHours'] == 124
    
    def test_non_apgd_scheme_a_gets_standard(self):
        """Test Scheme A without APO product gets standard limits"""
        from context.engine.constraint_config import get_monthly_hour_limits
        
        ctx = {
            'monthlyHourLimits': [
                {
                    'id': 'apgdMinimumContractualHours',
                    'applicableTo': {
                        'schemes': ['A'],
                        'productTypes': ['APO']
                    },
                    'valuesByMonthLength': {
                        '28': {'minimumContractualHours': 224}
                    }
                },
                {
                    'id': 'standardMonthlyHours',
                    'applicableTo': {'schemes': 'All'},
                    'valuesByMonthLength': {
                        '28': {'normalHours': 176}
                    }
                }
            ]
        }
        
        emp_no_apo = {'employeeId': 'E001', 'local': 1, 'scheme': 'A', 'productTypes': ['Standard']}
        limits = get_monthly_hour_limits(ctx, emp_no_apo, 2025, 2)
        
        assert limits['normalHours'] == 176
        assert limits['minimumContractualHours'] is None


class TestFrequencyAndUOM:
    """Test frequency and UOM metadata access"""
    
    def test_get_constraint_frequency(self):
        """Test reading frequency metadata"""
        from context.engine.constraint_config import get_constraint_frequency
        
        ctx = {
            'constraintList': [
                {
                    'id': 'momDailyHoursCap',
                    'frequency': 'Daily',
                    'uom': 'Hours',
                    'defaultValue': 9
                },
                {
                    'id': 'momWeeklyHoursCap44h',
                    'frequency': 'Weekly',
                    'uom': 'Hours',
                    'defaultValue': 44
                }
            ]
        }
        
        assert get_constraint_frequency(ctx, 'momDailyHoursCap') == 'Daily'
        assert get_constraint_frequency(ctx, 'momWeeklyHoursCap44h') == 'Weekly'
        assert get_constraint_frequency(ctx, 'nonexistent') is None
    
    def test_get_constraint_uom(self):
        """Test reading UOM metadata"""
        from context.engine.constraint_config import get_constraint_uom
        
        ctx = {
            'constraintList': [
                {
                    'id': 'momDailyHoursCap',
                    'frequency': 'Daily',
                    'uom': 'Hours',
                    'defaultValue': 9
                },
                {
                    'id': 'maxConsecutiveWorkingDays',
                    'frequency': 'Continuous',
                    'uom': 'Days',
                    'defaultValue': 12
                },
                {
                    'id': 'momLunchBreak',
                    'frequency': 'Per Shift',
                    'uom': 'Minutes',
                    'defaultValue': 60
                }
            ]
        }
        
        assert get_constraint_uom(ctx, 'momDailyHoursCap') == 'Hours'
        assert get_constraint_uom(ctx, 'maxConsecutiveWorkingDays') == 'Days'
        assert get_constraint_uom(ctx, 'momLunchBreak') == 'Minutes'
        assert get_constraint_uom(ctx, 'nonexistent') is None
    
    def test_get_constraint_metadata(self):
        """Test reading all constraint metadata"""
        from context.engine.constraint_config import get_constraint_metadata
        
        ctx = {
            'constraintList': [
                {
                    'id': 'momDailyHoursCap',
                    'enforcement': 'hard',
                    'description': 'Max daily hours',
                    'frequency': 'Daily',
                    'uom': 'Hours',
                    'defaultValue': 9,
                    'schemeOverrides': {'A': 14}
                }
            ]
        }
        
        metadata = get_constraint_metadata(ctx, 'momDailyHoursCap')
        
        assert metadata['id'] == 'momDailyHoursCap'
        assert metadata['enforcement'] == 'hard'
        assert metadata['frequency'] == 'Daily'
        assert metadata['uom'] == 'Hours'
        assert metadata['defaultValue'] == 9
        assert metadata['schemeOverrides'] == {'A': 14}
    
    def test_format_constraint_value(self):
        """Test formatting constraint values with UOM and frequency"""
        from context.engine.constraint_config import format_constraint_value
        
        # With both UOM and frequency
        assert format_constraint_value(44, 'Hours', 'Weekly') == '44 Hours /Weekly'
        
        # With UOM only
        assert format_constraint_value(8, 'Days') == '8 Days'
        
        # With frequency only
        assert format_constraint_value(1, frequency='Per Day') == '1 Per Day'
        
        # Without UOM or frequency
        assert format_constraint_value(12) == '12'
    
    def test_all_standard_frequencies(self):
        """Test all standard frequency values from Excel"""
        from context.engine.constraint_config import get_constraint_frequency
        
        ctx = {
            'constraintList': [
                {'id': 'daily', 'frequency': 'Daily'},
                {'id': 'weekly', 'frequency': 'Weekly'},
                {'id': 'monthly', 'frequency': 'Monthly'},
                {'id': 'perShift', 'frequency': 'Per Shift'},
                {'id': 'perDay', 'frequency': 'Per Day'},
                {'id': 'betweenShifts', 'frequency': 'Between Shifts'},
                {'id': 'continuous', 'frequency': 'Continuous'}
            ]
        }
        
        assert get_constraint_frequency(ctx, 'daily') == 'Daily'
        assert get_constraint_frequency(ctx, 'weekly') == 'Weekly'
        assert get_constraint_frequency(ctx, 'monthly') == 'Monthly'
        assert get_constraint_frequency(ctx, 'perShift') == 'Per Shift'
        assert get_constraint_frequency(ctx, 'perDay') == 'Per Day'
        assert get_constraint_frequency(ctx, 'betweenShifts') == 'Between Shifts'
        assert get_constraint_frequency(ctx, 'continuous') == 'Continuous'
    
    def test_all_standard_uoms(self):
        """Test all standard UOM values from Excel"""
        from context.engine.constraint_config import get_constraint_uom
        
        ctx = {
            'constraintList': [
                {'id': 'days', 'uom': 'Days'},
                {'id': 'hours', 'uom': 'Hours'},
                {'id': 'minutes', 'uom': 'Minutes'},
                {'id': 'number', 'uom': 'Number'}
            ]
        }
        
        assert get_constraint_uom(ctx, 'days') == 'Days'
        assert get_constraint_uom(ctx, 'hours') == 'Hours'
        assert get_constraint_uom(ctx, 'minutes') == 'Minutes'
        assert get_constraint_uom(ctx, 'number') == 'Number'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
