"""Slot Builder: Expand demandItems with rotation sequences into concrete daily shift slots.

Transforms the high-level demand specification (demand item + shift rotations) into
atomic "slot" objects representing each shift assignment opportunity on each day.

Example:
  Input: demandId=D001, rotationSequence=[D,D,N,N,O,O,O], startDate=2025-11-03
  Output: List of Slot objects for each (date, shiftCode) pair in the planning horizon
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta
import uuid


@dataclass
class Slot:
    """Represents a single shift slot to be filled.
    
    Attributes:
        slot_id: Unique identifier for this slot (demandId-requirementId-date-shiftCode-uuid)
        demandId: Reference to the demand item this slot fulfills
        requirementId: Reference to the specific requirement within the demand
        date: Date of the shift (calendar date)
        shiftCode: Shift code (e.g., 'D', 'N', 'O')
        start: Shift start time (datetime)
        end: Shift end time (datetime)
        locationId: Location where the shift is located
        ouId: Organizational unit
        productTypeId: Product type (e.g., 'APO', 'AVSO')
        rankIds: List of acceptable rank IDs (OR logic - employee must match ANY rank)
        genderRequirement: Gender requirement ('Any', 'M', 'F', 'Mix')
        schemeRequirement: Scheme requirement ('A', 'B', 'P', 'Global')
        requiredQualifications: List of required qualification codes
        rotationSequence: Rotation pattern for this requirement
        patternStartDate: Anchor date for rotation pattern calculation (shiftStartDate from demand)
        preferredTeams: List of preferred team IDs
        whitelist: Whitelist constraints {teamIds, employeeIds}
        blacklist: Blacklist with date ranges {employeeIds: [{employeeId, blacklistStartDate, blacklistEndDate}]}
    """
    slot_id: str
    demandId: str
    requirementId: str
    date: date
    shiftCode: str
    start: datetime
    end: datetime
    locationId: str
    ouId: str
    productTypeId: str
    rankIds: List[str]  # Changed from rankId (singular) to rankIds (plural) - supports multiple ranks
    genderRequirement: str
    schemeRequirement: str
    requiredQualifications: List[str]
    rotationSequence: List[str]
    patternStartDate: date
    coverageAnchor: date
    coverageDays: List[str]  # Day names this requirement covers (e.g., ['Monday', 'Tuesday', ...])
    preferredTeams: List[str]
    whitelist: Dict[str, List[str]]
    blacklist: Dict[str, List[Dict[str, str]]]


def combine(d: date, time_str: str) -> datetime:
    """Combine a date and time string (HH:MM format) into a datetime object.
    
    Args:
        d: Date object
        time_str: Time in 'HH:MM' format (e.g., '07:00')
    
    Returns:
        datetime object
    """
    parts = time_str.split(':')
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    return datetime.combine(d, datetime.min.time().replace(hour=hour, minute=minute))


def normalize_qualifications(required_quals) -> List[Dict[str, any]]:
    """Normalize qualification requirements to group format.
    
    Handles both formats:
    - Simple array: ["QUAL1", "QUAL2"] → single group with matchType="ALL"
    - Group format: [{"groupId": "...", "matchType": "ANY", "qualifications": [...]}]
    
    Args:
        required_quals: Either list of strings or list of group dicts
        
    Returns:
        List of qualification groups (always in group format)
    """
    if not required_quals:
        return []
    
    # Check if already in group format (first element is a dict with 'qualifications' key)
    if required_quals and isinstance(required_quals[0], dict) and 'qualifications' in required_quals[0]:
        # Already in group format - validate and return
        normalized = []
        for idx, group in enumerate(required_quals):
            normalized.append({
                'groupId': group.get('groupId', f'group_{idx}'),
                'matchType': group.get('matchType', 'ALL'),
                'qualifications': group.get('qualifications', [])
            })
        return normalized
    
    # Old format (simple array) - convert to single group with ALL logic
    if required_quals and isinstance(required_quals[0], str):
        return [{
            'groupId': 'default',
            'matchType': 'ALL',
            'qualifications': required_quals
        }]
    
    # Empty or invalid format
    return []


def normalize_scheme(scheme_value: str, scheme_map: Optional[Dict[str, str]] = None) -> str:
    """Normalize scheme value to short code format (A, B, P, or Global).
    
    Handles both formats (case-insensitive):
    - Full name: "Scheme A", "scheme A", "SCHEME A" → "A"
    - Short code: "A", "a" → "A"
    - Global: "Global", "global" → "Global"
    
    Args:
        scheme_value: The scheme value from input (can be "Scheme P" or "P" or "scheme p")
        scheme_map: Optional schemeMap from input (e.g., {"A": "Scheme A", "B": "Scheme B", "P": "Scheme P"})
    
    Returns:
        Normalized short code: "A", "B", "P", or "Global"
    """
    if not scheme_value:
        return "Global"
    
    # Handle "Global" case-insensitively
    if scheme_value.lower() == "global":
        return "Global"
    
    # If scheme_map is provided, try reverse lookup (case-insensitive)
    if scheme_map:
        # Check if value is already a short code (key in scheme_map) - case-insensitive
        for short_code in scheme_map.keys():
            if scheme_value.upper() == short_code.upper():
                return short_code  # Return the canonical short code from map
        
        # Try to find matching short code by value ("Scheme P" → "P") - case-insensitive
        for short_code, full_name in scheme_map.items():
            if full_name.lower() == scheme_value.lower():
                return short_code
    
    # Fallback: If it starts with "Scheme " (case-insensitive), extract the letter
    if scheme_value.lower().startswith("scheme "):
        extracted = scheme_value[7:].strip()  # Extract after "scheme "
        return extracted.upper()  # Normalize to uppercase
    
    # Already in short format
    return scheme_value


def daterange(start: date, end: date) -> List[date]:
    """Generate a list of dates from start (inclusive) to end (inclusive).
    
    Args:
        start: Start date
        end: End date
    
    Returns:
        List of date objects
    """
    current = start
    dates = []
    while current <= end:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def build_slots(inputs: Dict[str, Any]) -> List[Slot]:
    """Expand demandItems + requirements + shift rotations into concrete daily slots.
    
    Process (v0.70 schema):
    1. Parse planning horizon (startDate, endDate)
    2. For each demandItem:
       - Get shiftStartDate as rotation anchor
       - For each shift definition:
         - Map shiftCode → shift details (start time, end time, nextDay flag)
         - Get whitelist/blacklist from shift level
       - For each requirement:
         - Get rotation sequence per requirement
         - Get gender, scheme, qualifications per requirement
         - Create individual slots (headcount=1 each)
    3. For each day in planning horizon:
       - Determine which shift applies based on rotation offset
       - Create a Slot object for each position (NOT grouped by headcount)
    4. Return list of all slots
    
    Args:
        inputs: Input context dict with demandItems and planningHorizon
    
    Returns:
        List of Slot objects ready for assignment
    """
    horizon = inputs.get("planningHorizon", {})
    start_date = datetime.fromisoformat(horizon.get("startDate", "") + "T00:00:00").date()
    end_date = datetime.fromisoformat(horizon.get("endDate", "") + "T00:00:00").date()
    
    # Get public holidays from context
    public_holidays_str = inputs.get("publicHolidays", [])
    public_holidays = set()
    for ph_str in public_holidays_str:
        try:
            ph_date = datetime.fromisoformat(ph_str).date()
            public_holidays.add(ph_date)
        except:
            pass
    
    # Get schemeMap for normalizing scheme values
    scheme_map = inputs.get("schemeMap", {})
    
    slots: List[Slot] = []
    
    print(f"\n[slot_builder] Expanding demands into slots...")
    print(f"  Planning horizon: {start_date} to {end_date}")
    print(f"  Public holidays: {sorted(public_holidays)}")
    
    for dmd in inputs.get("demandItems", []):
        demand_id = dmd.get("demandId")
        location_id = dmd.get("locationId")
        ou_id = dmd.get("ouId")
        
        # Anchor date for rotation cycle
        base = datetime.fromisoformat(dmd.get("shiftStartDate", "") + "T00:00:00").date()
        
        print(f"  Demand {demand_id}: base={base}, location={location_id}")
        
        # Process each shift definition (get shift details, whitelist, blacklist)
        for shift_idx, sh in enumerate(dmd.get("shifts", [])):
            # Build map: shiftCode → shift details
            details = {}
            for sd in sh.get("shiftDetails", []):
                shift_code = sd.get("shiftCode")
                details[shift_code] = sd
            
            preferred_teams = sh.get("preferredTeams", [])
            whitelist = sh.get("whitelist", {"teamIds": [], "employeeIds": []})
            blacklist = sh.get("blacklist", {"employeeIds": []})
            
            # Get coverageDays - can be array of day names or legacy integer
            coverage_days_input = sh.get("coverageDays", 7)
            coverage_days_names = []
            coverage_anchor_str = sh.get("coverageAnchor")
            
            # Parse coverage anchor date (used for rotation cycle calculation)
            if coverage_anchor_str:
                try:
                    coverage_anchor_date = datetime.fromisoformat(coverage_anchor_str + "T00:00:00").date()
                except:
                    coverage_anchor_date = base
            else:
                coverage_anchor_date = base
            
            if isinstance(coverage_days_input, list):
                # New format: array of day names ["Mon", "Tue", "Wed", ...]
                coverage_days_names = coverage_days_input
                coverage_days_count = len(coverage_days_names)
            else:
                # Legacy format: integer (7 means all 7 days)
                coverage_days_count = coverage_days_input
                coverage_days_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][:coverage_days_count]
            
            # Get public holiday inclusion flags (default to True if not specified)
            include_public_holidays = sh.get("includePublicHolidays", True)
            include_eve_of_public_holidays = sh.get("includeEveOfPublicHolidays", True)
            
            print(f"    Shift #{shift_idx}: coverage_days={coverage_days_names}, includePH={include_public_holidays}, includeEvePH={include_eve_of_public_holidays}")
            
            # Process each requirement within this demand
            requirements = dmd.get("requirements", [])
            if not requirements:
                print(f"      ⚠️  No requirements found for demand {demand_id}, skipping")
                continue
            
            for req_idx, req in enumerate(requirements):
                requirement_id = req.get("requirementId", f"REQ{req_idx}")
                product_type = req.get("productTypeId")  # v0.70 schema uses productTypeId
                # Use normalized rankIds (plural) - already converted by data_loader
                rank_ids = req.get("rankIds", [])  # Changed from rankId to rankIds
                
                # Normalize headcount to support both formats:
                # Legacy: "headcount": 10 (single value for all shifts)
                # New: "headcount": {"D": 10, "N": 10} (per-shift headcount)
                headcount_raw = req.get("headcount", 1)
                
                # OUTCOME-BASED MODE OVERRIDE: Ignore requirement headcount, use employee count instead
                rostering_basis = inputs.get('_rosteringBasis', 'demandBased')
                if rostering_basis == 'outcomeBased':
                    # For outcomeBased, create one position per matching employee
                    # This ensures all employees can be assigned slots based on their pattern
                    employees = inputs.get('employees', [])
                    
                    # Filter employees by rank to match this requirement
                    # Note: employees use 'rankId' (singular), requirements use 'rankIds' (plural array)
                    matching_employees = [emp for emp in employees if emp.get('rankId') in rank_ids]
                    employee_based_headcount = len(matching_employees)
                    
                    print(f"      Requirement {requirement_id}: outcomeBased mode - overriding headcount")
                    print(f"        Original headcount: {headcount_raw}")
                    print(f"        Matching employees (rank={rank_ids}): {employee_based_headcount}")
                    print(f"        Using employee count as headcount")
                    
                    # Override headcount with employee count
                    headcount_raw = employee_based_headcount
                
                if isinstance(headcount_raw, dict):
                    # New format: per-shift headcount
                    headcount_by_shift = headcount_raw
                    print(f"      Requirement {requirement_id}: Using per-shift headcount {headcount_by_shift}")
                else:
                    # Legacy format: single headcount applies to all shifts
                    headcount_by_shift = {}  # Will be populated per shift code
                    default_headcount = headcount_raw
                
                gender_req = req.get("gender", "Any")
                # Normalize scheme value: "Scheme P" → "P", "Scheme A" → "A", etc.
                scheme_req_raw = req.get("Scheme", "Global")
                scheme_req = normalize_scheme(scheme_req_raw, scheme_map)
                
                # Normalize qualifications to group format (backwards compatible)
                required_quals_raw = req.get("requiredQualifications", [])
                required_quals = normalize_qualifications(required_quals_raw)
                
                # Support both old "rotationSequence" and new "workPattern" field names
                work_pattern = req.get("workPattern") or req.get("rotationSequence", [])
                
                if not work_pattern:
                    print(f"      ⚠️  Requirement {requirement_id} has empty work pattern, skipping")
                    continue
                
                print(f"      Requirement {requirement_id}: product={product_type}, ranks={rank_ids}, gender={gender_req}, scheme={scheme_req}")
                
                # Display headcount info
                if isinstance(headcount_raw, dict):
                    print(f"        Headcount (per-shift): {headcount_by_shift}")
                else:
                    print(f"        Headcount (legacy): {default_headcount} per shift")
                
                print(f"        Work Pattern: {work_pattern}")
                
                # Determine the shift code to use (first non-"O" code from sequence)
                non_o_codes = [code for code in work_pattern if code != "O"]
                default_shift_code = non_o_codes[0] if non_o_codes else list(details.keys())[0] if details else "D"
                
                # CRITICAL: coverageDays defines business need for continuous coverage
                # Slots must be created for ALL days in coverage window that match coverageDays
                # The rotation sequence is used for EMPLOYEE matching via rotationOffset
                # NOT for determining which days need slots!
                
                # Map day names to weekday indices
                day_name_to_idx = {
                    "Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6
                }
                coverage_weekdays = set(day_name_to_idx.get(d, -1) for d in coverage_days_names)
                
                # CRITICAL UNDERSTANDING:
                # 1. shiftDetails defines WHAT shifts exist (e.g., D and N = 2 shifts per day)
                # 2. coverageDays defines WHEN coverage is needed (e.g., Mon-Sun = every day)
                # 3. headcount defines HOW MANY people per shift (e.g., 2 = need 2 people)
                # 4. workPattern is ONLY for EMPLOYEE assignment logic (NOT slot creation)
                #
                # SLOT CREATION LOGIC:
                # SLOT CREATION LOGIC:
                # - Determine which shift codes to create based on workPattern
                # - If workPattern = ["D","D","D","D","O","O"] → Only create D slots
                # - If workPattern = ["N","N","N","N","O","O"] → Only create N slots
                # - If workPattern = ["D","D","N","N","O","O"] → Create both D and N slots
                # - Create headcount number of slots for each shift code that appears in workPattern
                
                # Extract unique shift codes from workPattern (excluding 'O')
                shift_codes_in_pattern = set()
                for code in work_pattern:
                    if code != 'O':
                        shift_codes_in_pattern.add(code)
                
                if not shift_codes_in_pattern:
                    print(f"      ⚠️  No shift codes found in workPattern (only 'O'), skipping")
                    continue
                
                # Verify these shift codes exist in shiftDetails
                available_shift_codes = list(details.keys())
                shift_codes_to_create = [code for code in shift_codes_in_pattern if code in available_shift_codes]
                
                if not shift_codes_to_create:
                    print(f"      ⚠️  Shift codes {shift_codes_in_pattern} from workPattern not found in shiftDetails, skipping")
                    continue
                
                print(f"        Creating slots for shift codes from workPattern: {sorted(shift_codes_to_create)}")
                
                # Generate slots for each shift code found in workPattern
                for shift_code in sorted(shift_codes_to_create):
                    shift_detail = details.get(shift_code)
                    if not shift_detail:
                        continue
                    
                    # Determine headcount for this specific shift code
                    if isinstance(headcount_raw, dict):
                        # New format: use per-shift headcount
                        shift_headcount = headcount_by_shift.get(shift_code, 0)
                        if shift_headcount == 0:
                            print(f"        ⚠️  Shift {shift_code} has 0 headcount, skipping")
                            continue
                    else:
                        # Legacy format: use default headcount for all shifts
                        shift_headcount = default_headcount
                    
                    print(f"        Creating {shift_headcount} position(s) for shift {shift_code}")
                    
                    # Parse shift times
                    start_time_str = shift_detail.get("start", "00:00")
                    end_time_str = shift_detail.get("end", "00:00")
                    next_day_flag = shift_detail.get("nextDay", False)
                    
                    # Generate slots for each position (shift_headcount times)
                    # Each slot is individual (headcount=1 per slot)
                    for position_idx in range(shift_headcount):
                        position_slot_count = 0
                        
                        for cur_day in daterange(start_date, end_date):
                            # Check if this day's weekday is in the coverage days
                            cur_weekday = cur_day.weekday()  # 0=Monday, 6=Sunday
                            if cur_weekday not in coverage_weekdays:
                                continue
                            
                            # Skip if current day is a public holiday and includePublicHolidays is False
                            if cur_day in public_holidays and not include_public_holidays:
                                continue
                            
                            # Skip if current day is eve of public holiday and includeEveOfPublicHolidays is False
                            next_day = cur_day + timedelta(days=1)
                            if next_day in public_holidays and not include_eve_of_public_holidays:
                                continue
                            
                            # Create shift start/end times
                            start = combine(cur_day, start_time_str)
                            end = combine(cur_day, end_time_str)
                            
                            # Handle overnight shifts
                            if end <= start or next_day_flag:
                                end = end + timedelta(days=1)
                            
                            # Create individual slot (headcount=1 per slot)
                            slot_id = f"{demand_id}-{requirement_id}-{shift_code}-P{position_idx}-{cur_day.isoformat()}-{uuid.uuid4().hex[:6]}"
                            slot = Slot(
                                slot_id=slot_id,
                                demandId=demand_id,
                                requirementId=requirement_id,
                                date=cur_day,
                                shiftCode=shift_code,
                                start=start,
                                end=end,
                                locationId=location_id,
                                ouId=ou_id,
                                productTypeId=product_type,
                                rankIds=rank_ids,  # Changed from rankId to rankIds
                                genderRequirement=gender_req,
                                schemeRequirement=scheme_req,
                                requiredQualifications=required_quals,
                                rotationSequence=work_pattern,
                                patternStartDate=base,
                                coverageAnchor=coverage_anchor_date,
                                coverageDays=coverage_days_names,
                                preferredTeams=preferred_teams,
                                whitelist=whitelist,
                                blacklist=blacklist
                            )
                            slots.append(slot)
                            position_slot_count += 1
                        
                        print(f"        Shift {shift_code}, Position {position_idx}: Created {position_slot_count} slots")
    
    print(f"[slot_builder] ✓ Expanded to {len(slots)} total slots\n")
    return slots


def print_slots(slots: List[Slot], limit: Optional[int] = None) -> None:
    """Pretty-print slot information for debugging.
    
    Args:
        slots: List of Slot objects
        limit: Max number of slots to print (None = all)
    """
    display_slots = slots[:limit] if limit else slots
    print(f"\n[Slots Summary] Total: {len(slots)}, Displaying: {len(display_slots)}")
    for slot in display_slots:
        print(f"  {slot.slot_id}")
        print(f"    Demand: {slot.demandId}, Requirement: {slot.requirementId}")
        print(f"    Date: {slot.date}, Shift: {slot.shiftCode}")
        print(f"    Time: {slot.start.strftime('%H:%M')} - {slot.end.strftime('%H:%M')} (next_day={slot.end.date() > slot.date})")
        print(f"    Location: {slot.locationId}, OU: {slot.ouId}")
        print(f"    Product: {slot.productTypeId}, Ranks: {slot.rankIds}")  # Changed to rankIds (plural)
        print(f"    Gender: {slot.genderRequirement}, Scheme: {slot.schemeRequirement}")
        print(f"    Required Qualifications: {slot.requiredQualifications}")
        if slot.preferredTeams:
            print(f"    Preferred Teams: {slot.preferredTeams}")
        if any(slot.whitelist.values()):
            print(f"    Whitelist: {slot.whitelist}")
        if slot.blacklist.get('employeeIds'):
            print(f"    Blacklist: {slot.blacklist}")
