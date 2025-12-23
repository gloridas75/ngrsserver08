"""
Test Suite for v0.96 Changes:
1. Multiple Schemes Support
2. APGD-D10 Automatic Detection
3. Cross-Mode Scheme Consistency

Run with: pytest tests/test_v096_changes.py -v
"""

import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pytest
from context.engine.time_utils import (
    normalize_schemes,
    is_scheme_compatible,
    is_apgd_d10_employee
)


class TestMultipleSchemes:
    """Test multiple schemes support (Change #1)"""
    
    def test_normalize_schemes_plural_format(self):
        """Test plural 'schemes' field with multiple values"""
        req = {'schemes': ['Scheme A', 'Scheme B']}
        result = normalize_schemes(req)
        assert result == ['A', 'B']
    
    def test_normalize_schemes_singular_backward_compatible(self):
        """Test backward compatibility with singular 'scheme' field"""
        req = {'scheme': 'Scheme A'}
        result = normalize_schemes(req)
        assert result == ['A']
    
    def test_normalize_schemes_global_to_any(self):
        """Test 'Global' converts to 'Any'"""
        req = {'scheme': 'Global'}
        result = normalize_schemes(req)
        assert result == ['Any']
    
    def test_normalize_schemes_any_keyword(self):
        """Test 'Any' keyword in plural format"""
        req = {'schemes': ['Any']}
        result = normalize_schemes(req)
        assert result == ['Any']
    
    def test_normalize_schemes_empty_list(self):
        """Test empty list means 'Any'"""
        req = {'schemes': []}
        result = normalize_schemes(req)
        assert result == ['Any']
    
    def test_normalize_schemes_priority(self):
        """Test plural 'schemes' takes priority over singular 'scheme'"""
        req = {'schemes': ['Scheme A', 'Scheme B'], 'scheme': 'Scheme P'}
        result = normalize_schemes(req)
        assert result == ['A', 'B']  # Should use plural, ignore singular
    
    def test_is_scheme_compatible_single_match(self):
        """Test employee matches single scheme requirement"""
        assert is_scheme_compatible('A', ['A']) == True
        assert is_scheme_compatible('B', ['A']) == False
    
    def test_is_scheme_compatible_multiple_match(self):
        """Test employee matches one of multiple schemes"""
        assert is_scheme_compatible('A', ['A', 'B']) == True
        assert is_scheme_compatible('B', ['A', 'B']) == True
        assert is_scheme_compatible('P', ['A', 'B']) == False
    
    def test_is_scheme_compatible_any(self):
        """Test 'Any' accepts all schemes"""
        assert is_scheme_compatible('A', ['Any']) == True
        assert is_scheme_compatible('B', ['Any']) == True
        assert is_scheme_compatible('P', ['Any']) == True


class TestAPGD_D10_Automatic:
    """Test APGD-D10 automatic detection (Change #2)"""
    
    def test_apgd_d10_scheme_a_apo(self):
        """Test APGD-D10 automatic for Scheme A + APO"""
        emp = {'scheme': 'Scheme A', 'productTypeId': 'APO'}
        assert is_apgd_d10_employee(emp) == True
    
    def test_apgd_d10_scheme_a_cvso(self):
        """Test APGD-D10 disabled for Scheme A + CVSO"""
        emp = {'scheme': 'Scheme A', 'productTypeId': 'CVSO'}
        assert is_apgd_d10_employee(emp) == False
    
    def test_apgd_d10_scheme_b_apo(self):
        """Test APGD-D10 disabled for Scheme B + APO"""
        emp = {'scheme': 'Scheme B', 'productTypeId': 'APO'}
        assert is_apgd_d10_employee(emp) == False
    
    def test_apgd_d10_scheme_p_apo(self):
        """Test APGD-D10 disabled for Scheme P + APO"""
        emp = {'scheme': 'Scheme P', 'productTypeId': 'APO'}
        assert is_apgd_d10_employee(emp) == False
    
    def test_apgd_d10_flag_ignored_true(self):
        """Test enableAPGD-D10=true flag is ignored (still automatic)"""
        emp = {'scheme': 'Scheme A', 'productTypeId': 'APO'}
        req = {'enableAPGD-D10': True}
        assert is_apgd_d10_employee(emp, req) == True
    
    def test_apgd_d10_flag_ignored_false(self):
        """Test enableAPGD-D10=false flag is IGNORED (APGD-D10 still enabled!)"""
        emp = {'scheme': 'Scheme A', 'productTypeId': 'APO'}
        req = {'enableAPGD-D10': False}
        # IMPORTANT: Flag is ignored, APGD-D10 still automatic for Scheme A + APO
        assert is_apgd_d10_employee(emp, req) == True
    
    def test_apgd_d10_no_flag(self):
        """Test APGD-D10 works without flag"""
        emp = {'scheme': 'Scheme A', 'productTypeId': 'APO'}
        req = {}  # No enableAPGD-D10 flag
        assert is_apgd_d10_employee(emp, req) == True
    
    def test_apgd_d10_no_requirement(self):
        """Test APGD-D10 works without requirement parameter"""
        emp = {'scheme': 'Scheme A', 'productTypeId': 'APO'}
        assert is_apgd_d10_employee(emp, None) == True


class TestRealWorldScenarios:
    """Test with real-world input scenarios"""
    
    def test_mixed_scheme_requirement(self):
        """Test requirement accepting Scheme A or B employees"""
        req = {'schemes': ['Scheme A', 'Scheme B']}
        schemes = normalize_schemes(req)
        
        # These should match
        assert is_scheme_compatible('A', schemes) == True
        assert is_scheme_compatible('B', schemes) == True
        
        # This should not match
        assert is_scheme_compatible('P', schemes) == False
    
    def test_12h_shift_scheme_filtering(self):
        """Test 12h shift requires Scheme A or B (not P with 9h cap)"""
        req = {'schemes': ['Scheme A', 'Scheme B']}  # Exclude Scheme P
        schemes = normalize_schemes(req)
        
        emp_a = {'scheme': 'Scheme A'}
        emp_b = {'scheme': 'Scheme B'}
        emp_p = {'scheme': 'Scheme P'}
        
        from context.engine.time_utils import normalize_scheme
        
        assert is_scheme_compatible(normalize_scheme(emp_a['scheme']), schemes) == True
        assert is_scheme_compatible(normalize_scheme(emp_b['scheme']), schemes) == True
        assert is_scheme_compatible(normalize_scheme(emp_p['scheme']), schemes) == False
    
    def test_apgd_d10_apo_operations(self):
        """Test APGD-D10 detection for APO security operations"""
        employees = [
            {'employeeId': '00001', 'scheme': 'Scheme A', 'productTypeId': 'APO'},
            {'employeeId': '00002', 'scheme': 'Scheme B', 'productTypeId': 'APO'},
            {'employeeId': '00003', 'scheme': 'Scheme A', 'productTypeId': 'CVSO'},
        ]
        
        apgd_employees = [emp for emp in employees if is_apgd_d10_employee(emp)]
        
        # Only employee 00001 (Scheme A + APO) should be APGD-D10
        assert len(apgd_employees) == 1
        assert apgd_employees[0]['employeeId'] == '00001'


class TestBackwardCompatibility:
    """Test backward compatibility with v0.95 inputs"""
    
    def test_old_singular_scheme_still_works(self):
        """Test v0.95 inputs with singular 'scheme' field still work"""
        req = {'scheme': 'Scheme A'}  # Old format
        schemes = normalize_schemes(req)
        assert schemes == ['A']
        assert is_scheme_compatible('A', schemes) == True
    
    def test_global_keyword_still_works(self):
        """Test 'Global' keyword still works (converts to 'Any')"""
        req = {'scheme': 'Global'}  # Old format
        schemes = normalize_schemes(req)
        assert schemes == ['Any']
        assert is_scheme_compatible('A', schemes) == True
        assert is_scheme_compatible('B', schemes) == True
        assert is_scheme_compatible('P', schemes) == True
    
    def test_apgd_d10_with_old_flag(self):
        """Test APGD-D10 still works with old enableAPGD-D10 flag"""
        emp = {'scheme': 'Scheme A', 'productTypeId': 'APO'}
        req = {'enableAPGD-D10': True}  # Old format (flag present)
        
        # Should work same as without flag
        assert is_apgd_d10_employee(emp, req) == True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
