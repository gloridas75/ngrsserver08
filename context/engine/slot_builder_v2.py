"""
v2 Slot Builder: Enhanced slot generation with dailyHeadcount support.

This module extends the v1 slot builder to support variable daily headcount
for demand-based rostering. It reads the dailyHeadcount array from requirements
and creates the appropriate number of slots per day.

Key Features:
- dailyHeadcount: Array of {date, shiftCode, headcount, dayType} objects
- dayType: "Normal", "PublicHoliday", "EveOfPH" (informational)
- Backward compatible: Falls back to static headcount if dailyHeadcount missing
- Only applies to demandBased mode (outcomeBased uses employee-based slots)

Schema (v0.98+):
{
  "requirements": [{
    "requirementId": "346_1",
    "headcount": 5,  // Fallback if dailyHeadcount missing
    "dailyHeadcount": [
      {"date": "2026-02-01", "shiftCode": "D", "headcount": 5, "dayType": "Normal"},
      {"date": "2026-02-17", "shiftCode": "D", "headcount": 3, "dayType": "PublicHoliday"}
    ],
    "workPattern": ["D","D","D","D","D","O","O"]
  }]
}
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta
import uuid
import logging

# Import base Slot class and utilities from v1 slot builder
from context.engine.slot_builder import (
    Slot, combine, daterange, normalize_qualifications, normalize_scheme,
    _build_employee_based_slots
)

logger = logging.getLogger("ngrs.slot_builder.v2")


@dataclass
class DailyHeadcountEntry:
    """Represents a single entry in the dailyHeadcount array."""
    date: date
    shift_code: str
    headcount: int
    day_type: str  # "Normal", "PublicHoliday", "EveOfPH"
    start_time_override: Optional[str] = None  # "HH:MM" or "HH:MM:SS" format
    end_time_override: Optional[str] = None    # "HH:MM" or "HH:MM:SS" format
    reason: Optional[str] = None               # Optional reason for override


def parse_daily_headcount(daily_headcount_raw: List[Dict[str, Any]]) -> Dict[tuple, DailyHeadcountEntry]:
    """
    Parse dailyHeadcount array into a lookup dictionary.
    
    Args:
        daily_headcount_raw: List of {date, shiftCode, headcount, dayType, startTimeOverride?, endTimeOverride?, reason?} dicts
        
    Returns:
        Dict mapping (date, shiftCode) tuple to DailyHeadcountEntry
    """
    lookup = {}
    
    for entry in daily_headcount_raw:
        date_str = entry.get('date', '')
        shift_code = entry.get('shiftCode', '')
        headcount = entry.get('headcount', 0)
        day_type = entry.get('dayType', 'Normal')
        
        # v2 enhancement: time overrides
        start_time_override = entry.get('startTimeOverride')
        end_time_override = entry.get('endTimeOverride')
        reason = entry.get('reason')
        
        if not date_str or not shift_code:
            continue
        
        try:
            entry_date = datetime.fromisoformat(date_str).date()
        except ValueError:
            # Try parsing as date without time
            try:
                entry_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                logger.warning(f"Invalid date format in dailyHeadcount: {date_str}")
                continue
        
        key = (entry_date, shift_code)
        lookup[key] = DailyHeadcountEntry(
            date=entry_date,
            shift_code=shift_code,
            headcount=headcount,
            day_type=day_type,
            start_time_override=start_time_override,
            end_time_override=end_time_override,
            reason=reason
        )
        
        # Log time overrides when present
        if start_time_override or end_time_override:
            logger.info(f"    Time override on {entry_date}: {start_time_override or 'default'} - {end_time_override or 'default'}")
    
    return lookup


def build_slots_v2(inputs: Dict[str, Any]) -> List[Slot]:
    """
    Build slots with dailyHeadcount support for demand-based rostering.
    
    This is the v2 slot builder that supports variable headcount per day.
    For demandBased mode, it reads dailyHeadcount and creates the appropriate
    number of slots per (date, shiftCode) combination.
    
    Key differences from v1:
    - Reads dailyHeadcount array if present
    - Creates variable slots per day based on dailyHeadcount
    - Stores dayType in slot for output enrichment
    - Falls back to static headcount if dailyHeadcount missing
    
    Args:
        inputs: Input context dict with demandItems and planningHorizon
        
    Returns:
        List of Slot objects ready for assignment
    """
    horizon = inputs.get("planningHorizon", {})
    start_date = datetime.fromisoformat(horizon.get("startDate", "") + "T00:00:00").date()
    end_date = datetime.fromisoformat(horizon.get("endDate", "") + "T00:00:00").date()
    
    # Get public holidays
    public_holidays_str = inputs.get("publicHolidays", [])
    public_holidays = set()
    for ph_str in public_holidays_str:
        try:
            ph_date = datetime.fromisoformat(ph_str).date()
            public_holidays.add(ph_date)
        except:
            pass
    
    scheme_map = inputs.get("schemeMap", {})
    slots: List[Slot] = []
    
    logger.info(f"[slot_builder_v2] Building slots with dailyHeadcount support...")
    logger.info(f"  Planning horizon: {start_date} to {end_date}")
    logger.info(f"  Public holidays: {sorted(public_holidays)}")
    
    # Check rostering basis - dailyHeadcount only applies to demandBased
    rostering_basis = inputs.get('_rosteringBasis', 'demandBased')
    
    # For outcomeBased with employee-based slots, delegate to v1 builder
    if inputs.get('_useEmployeeBasedSlots', False):
        logger.info("  Using employee-based slot generation (outcomeBased mode)")
        return _build_employee_based_slots(inputs, start_date, end_date, public_holidays)
    
    for dmd in inputs.get("demandItems", []):
        demand_id = dmd.get("demandId")
        location_id = dmd.get("locationId")
        ou_id = dmd.get("ouId")
        demand_rostering_basis = dmd.get("rosteringBasis", rostering_basis)
        
        # Anchor date for rotation cycle
        base_str = dmd.get("shiftStartDate", "")
        base = datetime.fromisoformat(base_str + "T00:00:00").date() if base_str else start_date
        
        logger.info(f"  Demand {demand_id}: rosteringBasis={demand_rostering_basis}, base={base}")
        
        # Skip dailyHeadcount processing for outcomeBased
        use_daily_headcount = (demand_rostering_basis == 'demandBased')
        
        for shift_idx, sh in enumerate(dmd.get("shifts", [])):
            # Build shift details map
            details = {}
            for sd in sh.get("shiftDetails", []):
                shift_code = sd.get("shiftCode")
                details[shift_code] = sd
            
            preferred_teams = sh.get("preferredTeams", [])
            whitelist = sh.get("whitelist", {"teamIds": [], "employeeIds": []})
            blacklist = sh.get("blacklist", {"employeeIds": []})
            
            # Get coverage days
            coverage_days_input = sh.get("coverageDays", 7)
            if isinstance(coverage_days_input, list):
                coverage_days_names = coverage_days_input
            else:
                coverage_days_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][:coverage_days_input]
            
            # Coverage anchor
            coverage_anchor_str = sh.get("coverageAnchor")
            if coverage_anchor_str:
                try:
                    coverage_anchor_date = datetime.fromisoformat(coverage_anchor_str + "T00:00:00").date()
                except:
                    coverage_anchor_date = base
            else:
                coverage_anchor_date = base
            
            # Public holiday flags
            include_public_holidays = sh.get("includePublicHolidays", True)
            include_eve_of_public_holidays = sh.get("includeEveOfPublicHolidays", True)
            
            # Day name to weekday index mapping
            day_name_to_idx = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
            coverage_weekdays = set(day_name_to_idx.get(d, -1) for d in coverage_days_names)
            
            # Process each requirement
            for req_idx, req in enumerate(dmd.get("requirements", [])):
                requirement_id = req.get("requirementId", f"REQ{req_idx}")
                
                # === v2 CHANGE: Support productTypeIds array (OR logic) ===
                # If productTypeIds array is present, it takes precedence
                # Otherwise fall back to single productTypeId for backward compatibility
                product_type_ids = req.get("productTypeIds", [])
                product_type = req.get("productTypeId")
                
                # Log product type configuration
                if product_type_ids:
                    logger.info(f"    Requirement {requirement_id}: Multiple product types (OR): {product_type_ids}")
                elif product_type:
                    logger.info(f"    Requirement {requirement_id}: Single product type: {product_type}")
                
                rank_ids = req.get("rankIds", [])
                gender_req = req.get("gender", "Any")
                
                # Normalize scheme
                scheme_req_raw = None
                if "schemes" in req:
                    schemes_list = req.get("schemes", [])
                    if isinstance(schemes_list, list) and schemes_list:
                        if len(schemes_list) > 1 or schemes_list[0].upper() in ('ANY', 'GLOBAL', 'ALL'):
                            scheme_req_raw = "Global"
                        else:
                            scheme_req_raw = schemes_list[0]
                    else:
                        scheme_req_raw = "Global"
                else:
                    scheme_req_raw = "Global"
                scheme_req = normalize_scheme(scheme_req_raw)
                
                # Normalize qualifications
                required_quals = normalize_qualifications(req.get("requiredQualifications", []))
                
                # Get work pattern
                work_pattern = req.get("workPattern") or req.get("rotationSequence", [])
                if not work_pattern:
                    logger.warning(f"  ⚠️  Requirement {requirement_id} has no work pattern, skipping")
                    continue
                
                # === v2 CHANGE: Parse dailyHeadcount ===
                daily_headcount_raw = req.get("dailyHeadcount", [])
                static_headcount = req.get("headcount", 1)
                
                if use_daily_headcount and daily_headcount_raw:
                    daily_hc_lookup = parse_daily_headcount(daily_headcount_raw)
                    logger.info(f"    Requirement {requirement_id}: Using dailyHeadcount ({len(daily_hc_lookup)} entries)")
                else:
                    daily_hc_lookup = {}
                    logger.info(f"    Requirement {requirement_id}: Using static headcount={static_headcount}")
                
                # Extract shift codes from work pattern
                shift_codes_in_pattern = set(code for code in work_pattern if code != 'O')
                if not shift_codes_in_pattern:
                    logger.warning(f"    ⚠️  No shift codes in workPattern, skipping")
                    continue
                
                # Verify shift codes exist
                shift_codes_to_create = [code for code in shift_codes_in_pattern if code in details]
                if not shift_codes_to_create:
                    logger.warning(f"    ⚠️  Shift codes {shift_codes_in_pattern} not in shiftDetails, skipping")
                    continue
                
                logger.info(f"      Shift codes: {sorted(shift_codes_to_create)}")
                
                # Generate slots
                for shift_code in sorted(shift_codes_to_create):
                    shift_detail = details.get(shift_code)
                    if not shift_detail:
                        continue
                    
                    start_time_str = shift_detail.get("start", "00:00")
                    end_time_str = shift_detail.get("end", "00:00")
                    next_day_flag = shift_detail.get("nextDay", False)
                    
                    slots_created_for_shift = 0
                    
                    for cur_day in daterange(start_date, end_date):
                        # Check coverage day
                        cur_weekday = cur_day.weekday()
                        if cur_weekday not in coverage_weekdays:
                            continue
                        
                        # Check public holiday exclusion
                        if cur_day in public_holidays and not include_public_holidays:
                            continue
                        
                        # Check eve of PH exclusion
                        next_day = cur_day + timedelta(days=1)
                        if next_day in public_holidays and not include_eve_of_public_holidays:
                            continue
                        
                        # === v2 CHANGE: Get headcount from dailyHeadcount or fallback ===
                        key = (cur_day, shift_code)
                        day_start_override = None
                        day_end_override = None
                        
                        if key in daily_hc_lookup:
                            entry = daily_hc_lookup[key]
                            day_headcount = entry.headcount
                            day_type = entry.day_type
                            # Get time overrides if present
                            day_start_override = entry.start_time_override
                            day_end_override = entry.end_time_override
                        else:
                            # Fallback to static headcount
                            day_headcount = static_headcount
                            # Infer day_type from public holidays
                            if cur_day in public_holidays:
                                day_type = "PublicHoliday"
                            elif next_day in public_holidays:
                                day_type = "EveOfPH"
                            else:
                                day_type = "Normal"
                        
                        # Skip if headcount is 0
                        if day_headcount <= 0:
                            continue
                        
                        # Create slots for each position
                        for position_idx in range(day_headcount):
                            # === v2 CHANGE: Apply time overrides if present ===
                            # Use override times if provided, otherwise use default shift times
                            actual_start_time = day_start_override if day_start_override else start_time_str
                            actual_end_time = day_end_override if day_end_override else end_time_str
                            
                            # Create shift times with potential overrides
                            slot_start = combine(cur_day, actual_start_time)
                            slot_end = combine(cur_day, actual_end_time)
                            
                            # Handle overnight shifts
                            if slot_end <= slot_start or next_day_flag:
                                slot_end = slot_end + timedelta(days=1)
                            
                            # Create slot with dayType metadata
                            slot_id = f"{demand_id}-{requirement_id}-{shift_code}-P{position_idx}-{cur_day.isoformat()}-{uuid.uuid4().hex[:6]}"
                            
                            slot = Slot(
                                slot_id=slot_id,
                                demandId=demand_id,
                                requirementId=requirement_id,
                                date=cur_day,
                                shiftCode=shift_code,
                                start=slot_start,
                                end=slot_end,
                                locationId=location_id,
                                ouId=ou_id,
                                productTypeId=product_type,
                                rankIds=rank_ids,
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
                            
                            # Store dayType as metadata on slot for output enrichment
                            slot._dayType = day_type
                            
                            # === v2 CHANGE: Store productTypeIds array for OR matching ===
                            # This allows solver_engine to match employee against multiple product types
                            slot._productTypeIds = product_type_ids if product_type_ids else None
                            
                            # Store time override flag for output enrichment
                            slot._hasTimeOverride = (day_start_override is not None or day_end_override is not None)
                            
                            slots.append(slot)
                            slots_created_for_shift += 1
                    
                    logger.info(f"      Shift {shift_code}: Created {slots_created_for_shift} slots")
    
    # Log summary with headcount variation stats
    if slots:
        dates_with_slots = set(s.date for s in slots)
        shifts_with_slots = set(s.shiftCode for s in slots)
        
        logger.info(f"[slot_builder_v2] ✓ Created {len(slots)} total slots")
        logger.info(f"  Dates covered: {min(dates_with_slots)} to {max(dates_with_slots)}")
        logger.info(f"  Shift codes: {sorted(shifts_with_slots)}")
        
        # Show headcount variation
        slots_per_day = {}
        for s in slots:
            key = (s.date, s.shiftCode)
            slots_per_day[key] = slots_per_day.get(key, 0) + 1
        
        headcounts = list(slots_per_day.values())
        if headcounts:
            min_hc = min(headcounts)
            max_hc = max(headcounts)
            if min_hc != max_hc:
                logger.info(f"  Headcount range: {min_hc} to {max_hc} (variable)")
            else:
                logger.info(f"  Headcount: {min_hc} (uniform)")
    
    return slots
