"""C7: License/qualification must be valid on shift date.

Enforce that employees can only be assigned to shifts requiring qualifications
they actually hold and that are currently valid (not expired).

Supports both simple qualifications and qualification groups:
- Simple: ["QUAL1", "QUAL2"] - employee must have ALL
- Groups: [{"groupId": "g1", "matchType": "ANY", "qualifications": ["Q1", "Q2"]}]
  - matchType="ALL": employee must have ALL qualifications in group
  - matchType="ANY": employee must have AT LEAST ONE qualification in group

Input Schema (v0.70):
- employees: [{ employeeId, licenses: [{ code, expiryDate }], ... }]
- Slot objects have requiredQualifications (normalized to group format)
- planningHorizon: { startDate, endDate }
"""
from datetime import datetime


def has_valid_qualification(emp_licenses, qual_code, slot_date):
    """Check if employee has a valid (non-expired) qualification.
    
    Args:
        emp_licenses: Dict mapping qual codes to expiry dates
        qual_code: Qualification code to check
        slot_date: Date of the shift
        
    Returns:
        bool: True if employee has the qualification and it's not expired
    """
    if qual_code not in emp_licenses:
        return False
    
    expiry_date_str = emp_licenses[qual_code]
    try:
        expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
        # Qualification is valid if shift date is on or before expiry date
        return slot_date <= expiry_date
    except (ValueError, AttributeError):
        # Failed to parse expiry date - treat as invalid
        return False


def evaluate_qualification_groups(emp_licenses, qual_groups, slot_date):
    """Check if employee meets all qualification group requirements.
    
    Args:
        emp_licenses: Dict mapping qual codes to expiry dates for employee
        qual_groups: List of qualification groups (normalized format)
        slot_date: Date of the shift
        
    Returns:
        bool: True if employee satisfies all groups
    """
    if not qual_groups:
        return True  # No requirements
    
    for group in qual_groups:
        match_type = group.get('matchType', 'ALL')
        required_quals = group.get('qualifications', [])
        
        if not required_quals:
            continue  # Empty group, skip
        
        if match_type == 'ALL':
            # Employee must have ALL qualifications in this group
            for qual in required_quals:
                if not has_valid_qualification(emp_licenses, qual, slot_date):
                    return False  # Missing or expired qualification
        
        elif match_type == 'ANY':
            # Employee must have AT LEAST ONE qualification in this group
            has_any = False
            for qual in required_quals:
                if has_valid_qualification(emp_licenses, qual, slot_date):
                    has_any = True
                    break
            
            if not has_any:
                return False  # No valid qualification from this group
        
        else:
            # Unknown match type - treat as ALL for safety
            for qual in required_quals:
                if not has_valid_qualification(emp_licenses, qual, slot_date):
                    return False
    
    return True  # All groups satisfied


def add_constraints(model, ctx):
    """
    Enforce that employees have valid licenses/qualifications for assigned shifts (HARD).
    
    This constraint ensures that:
    1. Employee has the required qualification in their credentials
    2. The qualification has not expired on the shift date
    
    Args:
        model: CP-SAT model from ortools
        ctx: Context dict with planning data
    """
    
    employees = ctx.get('employees', [])
    slots = ctx.get('slots', [])
    x = ctx.get('x', {})
    
    if not slots or not x:
        print(f"[C7] Warning: Slots or decision variables not available")
        return
    
    # Build employee license map: emp_id -> {license_code -> expiry_date}
    # v0.70: Check both 'licenses' and 'qualifications' fields for compatibility
    employee_licenses = {}
    for emp in employees:
        emp_id = emp.get('employeeId')
        licenses = {}
        
        # Check 'licenses' field (old schema)
        for lic in emp.get('licenses', []):
            code = lic.get('code')
            expiry = lic.get('expiryDate')
            if code and expiry:
                licenses[code] = expiry
        
        # Also check 'qualifications' field (v0.70 schema)
        for qual in emp.get('qualifications', []):
            code = qual.get('code')
            expiry = qual.get('expiryDate')
            if code and expiry:
                licenses[code] = expiry
        
        employee_licenses[emp_id] = licenses
    
    # Add constraints: for each slot-employee pair, verify qualifications
    # v0.70: requiredQualifications is normalized to group format by slot_builder
    license_constraints = 0
    for slot in slots:
        slot_date = slot.date  # This is a date object from Slot dataclass
        qual_groups = getattr(slot, 'requiredQualifications', [])
        
        # Skip if no qualifications required for this slot
        if not qual_groups:
            continue
        
        for emp in employees:
            emp_id = emp.get('employeeId')
            emp_licenses = employee_licenses.get(emp_id, {})
            
            if (slot.slot_id, emp_id) not in x:
                continue
            
            # Check if employee meets all qualification group requirements
            has_valid_quals = evaluate_qualification_groups(emp_licenses, qual_groups, slot_date)
            
            # If employee doesn't have valid qualifications, block assignment
            if not has_valid_quals:
                var = x[(slot.slot_id, emp_id)]
                # Add constraint: var must be 0 (not assigned)
                model.Add(var == 0)
                license_constraints += 1
    
    # Collect statistics
    employees_with_licenses = sum(1 for emp in employees if (emp.get('licenses', []) or emp.get('qualifications', [])))
    slots_with_quals = sum(1 for s in slots if getattr(s, 'requiredQualifications', []))
    
    # Count qual groups for detailed stats
    total_groups = 0
    any_groups = 0
    all_groups = 0
    for slot in slots:
        qual_groups = getattr(slot, 'requiredQualifications', [])
        total_groups += len(qual_groups)
        for group in qual_groups:
            if group.get('matchType') == 'ANY':
                any_groups += 1
            else:
                all_groups += 1
    
    print(f"[C7] License Validity Constraint (HARD)")
    print(f"     Employees: {len(employees)} ({employees_with_licenses} have licenses)")
    print(f"     Slots: {len(slots)} ({slots_with_quals} require qualifications)")
    print(f"     Qualification Groups: {total_groups} total ({all_groups} ALL, {any_groups} ANY)")
    print(f"     Blocked Assignments: {license_constraints}")
    print(f"     Slots: {len(slots)} ({slots_with_quals} require qualifications)")
    print(f"     ✓ Added {license_constraints} license validity constraints\n")
