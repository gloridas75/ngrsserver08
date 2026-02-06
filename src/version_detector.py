"""
API Version Detection and dailyHeadcount Validation.

This module provides:
1. Auto-detection of v2 features (dailyHeadcount) in input JSON
2. Validation rules for dailyHeadcount entries
3. Helper functions for version routing

The goal is to allow frontend to continue using root endpoints (/solve, /solve/async)
while the backend automatically routes to v2 processing when dailyHeadcount is present.
"""

import logging
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, date
from dataclasses import dataclass, field

logger = logging.getLogger("ngrs.version_detector")


@dataclass
class DailyHeadcountValidation:
    """Result of dailyHeadcount validation."""
    is_valid: bool = True
    has_daily_headcount: bool = False
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    
    def add_error(self, code: str, message: str, field: str = "", context: Dict = None):
        """Add validation error."""
        self.is_valid = False
        self.errors.append({
            "code": code,
            "message": message,
            "field": field,
            "severity": "error",
            "context": context or {}
        })
    
    def add_warning(self, code: str, message: str, field: str = "", context: Dict = None):
        """Add validation warning (doesn't block processing)."""
        self.warnings.append({
            "code": code,
            "message": message,
            "field": field,
            "severity": "warning",
            "context": context or {}
        })


def detect_api_version(input_json: Dict[str, Any]) -> Tuple[str, bool, Dict[str, Any]]:
    """
    Detect which API version to use based on input features.
    
    Auto-detection rules:
    1. If explicit 'apiVersion' field is present, use it
    2. If any requirement has 'dailyHeadcount' array, use v2
    3. Otherwise, use v1 (backward compatible)
    
    Args:
        input_json: The solver input JSON
        
    Returns:
        Tuple of (api_version, has_daily_headcount, detection_info)
        - api_version: "v1" or "v2"
        - has_daily_headcount: True if dailyHeadcount is present
        - detection_info: Dict with detection details
    """
    detection_info = {
        "explicit_version": None,
        "has_daily_headcount": False,
        "daily_headcount_count": 0,
        "requirements_with_daily_hc": 0,
        "detection_reason": ""
    }
    
    # Check for explicit apiVersion field
    explicit_version = input_json.get("apiVersion")
    if explicit_version:
        detection_info["explicit_version"] = explicit_version
        detection_info["detection_reason"] = f"Explicit apiVersion={explicit_version} in input"
        return explicit_version, False, detection_info
    
    # Check for dailyHeadcount in any requirement
    has_daily_headcount = False
    total_daily_hc_entries = 0
    requirements_with_daily_hc = 0
    
    for dmd in input_json.get("demandItems", []):
        for req in dmd.get("requirements", []):
            daily_hc = req.get("dailyHeadcount", [])
            if daily_hc and isinstance(daily_hc, list) and len(daily_hc) > 0:
                has_daily_headcount = True
                requirements_with_daily_hc += 1
                total_daily_hc_entries += len(daily_hc)
    
    detection_info["has_daily_headcount"] = has_daily_headcount
    detection_info["daily_headcount_count"] = total_daily_hc_entries
    detection_info["requirements_with_daily_hc"] = requirements_with_daily_hc
    
    if has_daily_headcount:
        detection_info["detection_reason"] = (
            f"Auto-detected v2: Found dailyHeadcount in {requirements_with_daily_hc} requirement(s) "
            f"with {total_daily_hc_entries} total entries"
        )
        return "v2", True, detection_info
    else:
        detection_info["detection_reason"] = "No dailyHeadcount found, using v1 (static headcount)"
        return "v1", False, detection_info


def validate_daily_headcount(input_json: Dict[str, Any]) -> DailyHeadcountValidation:
    """
    Validate dailyHeadcount entries in input JSON.
    
    Validation rules:
    1. Date range: All dates must be within planningHorizon
    2. Shift code: Must exist in corresponding shiftDetails
    3. Headcount: Must be >= 0
    4. dayType: Must be "Normal", "PublicHoliday", or "EveOfPH"
    5. Coverage: Warn if dates are missing (will use fallback)
    6. PH consistency: Warn if dayType=PublicHoliday but date not in publicHolidays
    
    Args:
        input_json: The solver input JSON
        
    Returns:
        DailyHeadcountValidation result
    """
    result = DailyHeadcountValidation()
    
    # Get planning horizon
    horizon = input_json.get("planningHorizon", {})
    try:
        start_date = datetime.fromisoformat(horizon.get("startDate", "")).date()
        end_date = datetime.fromisoformat(horizon.get("endDate", "")).date()
    except (ValueError, TypeError):
        result.add_error(
            "INVALID_HORIZON",
            "Cannot validate dailyHeadcount: Invalid planningHorizon",
            "planningHorizon"
        )
        return result
    
    # Get public holidays
    public_holidays = set()
    for ph_str in input_json.get("publicHolidays", []):
        try:
            ph_date = datetime.fromisoformat(ph_str).date()
            public_holidays.add(ph_date)
        except:
            pass
    
    # Valid dayType values
    valid_day_types = {"Normal", "PublicHoliday", "EveOfPH"}
    
    # Track coverage for warnings
    total_requirements_with_dhc = 0
    total_entries = 0
    dates_covered = set()
    
    for dmd_idx, dmd in enumerate(input_json.get("demandItems", [])):
        demand_id = dmd.get("demandId", f"demand_{dmd_idx}")
        
        # Get shift details for this demand
        shift_codes_available = set()
        for shift_set in dmd.get("shifts", []):
            for sd in shift_set.get("shiftDetails", []):
                shift_codes_available.add(sd.get("shiftCode"))
        
        for req_idx, req in enumerate(dmd.get("requirements", [])):
            requirement_id = req.get("requirementId", f"req_{req_idx}")
            daily_hc = req.get("dailyHeadcount", [])
            
            if not daily_hc or not isinstance(daily_hc, list):
                continue
            
            result.has_daily_headcount = True
            total_requirements_with_dhc += 1
            
            # Track dates for this requirement to check coverage
            dates_in_dhc = set()
            
            for entry_idx, entry in enumerate(daily_hc):
                total_entries += 1
                field_prefix = f"demandItems[{dmd_idx}].requirements[{req_idx}].dailyHeadcount[{entry_idx}]"
                
                # Validate date
                date_str = entry.get("date", "")
                entry_date = None
                
                try:
                    entry_date = datetime.fromisoformat(date_str).date()
                except (ValueError, TypeError):
                    try:
                        entry_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    except:
                        result.add_error(
                            "INVALID_DATE_FORMAT",
                            f"Invalid date format: {date_str}",
                            f"{field_prefix}.date",
                            {"date": date_str}
                        )
                        continue
                
                # Check date within horizon
                if entry_date < start_date or entry_date > end_date:
                    result.add_error(
                        "DATE_OUT_OF_RANGE",
                        f"Date {date_str} is outside planning horizon ({start_date} to {end_date})",
                        f"{field_prefix}.date",
                        {"date": date_str, "start": str(start_date), "end": str(end_date)}
                    )
                
                dates_in_dhc.add(entry_date)
                dates_covered.add(entry_date)
                
                # Validate shiftCode
                shift_code = entry.get("shiftCode", "")
                if not shift_code:
                    result.add_error(
                        "MISSING_SHIFT_CODE",
                        "shiftCode is required",
                        f"{field_prefix}.shiftCode"
                    )
                elif shift_codes_available and shift_code not in shift_codes_available:
                    result.add_error(
                        "INVALID_SHIFT_CODE",
                        f"shiftCode '{shift_code}' not found in shiftDetails. Available: {sorted(shift_codes_available)}",
                        f"{field_prefix}.shiftCode",
                        {"shiftCode": shift_code, "available": sorted(shift_codes_available)}
                    )
                
                # Validate headcount
                headcount = entry.get("headcount")
                if headcount is None:
                    result.add_error(
                        "MISSING_HEADCOUNT",
                        "headcount is required",
                        f"{field_prefix}.headcount"
                    )
                elif not isinstance(headcount, (int, float)) or headcount < 0:
                    result.add_error(
                        "INVALID_HEADCOUNT",
                        f"headcount must be a non-negative number, got: {headcount}",
                        f"{field_prefix}.headcount",
                        {"headcount": headcount}
                    )
                
                # Validate dayType
                day_type = entry.get("dayType", "Normal")
                if day_type not in valid_day_types:
                    result.add_warning(
                        "INVALID_DAY_TYPE",
                        f"Invalid dayType '{day_type}', defaulting to 'Normal'. Valid values: {sorted(valid_day_types)}",
                        f"{field_prefix}.dayType",
                        {"dayType": day_type, "valid": sorted(valid_day_types)}
                    )
                
                # Check PH consistency
                if entry_date:
                    if day_type == "PublicHoliday" and entry_date not in public_holidays:
                        result.add_warning(
                            "PH_INCONSISTENCY",
                            f"dayType=PublicHoliday but {date_str} is not in publicHolidays array",
                            f"{field_prefix}.dayType",
                            {"date": date_str, "publicHolidays": sorted([str(d) for d in public_holidays])}
                        )
                    elif day_type == "Normal" and entry_date in public_holidays:
                        result.add_warning(
                            "PH_MISMATCH",
                            f"dayType=Normal but {date_str} is in publicHolidays array",
                            f"{field_prefix}.dayType",
                            {"date": date_str}
                        )
            
            # Check coverage completeness (warn if dates missing)
            all_horizon_dates = set()
            current = start_date
            from datetime import timedelta
            while current <= end_date:
                all_horizon_dates.add(current)
                current += timedelta(days=1)
            
            missing_dates = all_horizon_dates - dates_in_dhc
            if missing_dates:
                fallback_hc = req.get("headcount", 1)
                result.add_warning(
                    "INCOMPLETE_COVERAGE",
                    f"Requirement {requirement_id}: {len(missing_dates)} dates missing from dailyHeadcount. "
                    f"Will use fallback headcount={fallback_hc}",
                    f"demandItems[{dmd_idx}].requirements[{req_idx}].dailyHeadcount",
                    {
                        "missingCount": len(missing_dates),
                        "fallbackHeadcount": fallback_hc,
                        "firstMissing": str(min(missing_dates)),
                        "lastMissing": str(max(missing_dates))
                    }
                )
    
    # Build summary
    result.summary = {
        "requirementsWithDailyHeadcount": total_requirements_with_dhc,
        "totalEntries": total_entries,
        "datesWithCoverage": len(dates_covered),
        "planningHorizonDays": (end_date - start_date).days + 1,
        "publicHolidaysCount": len(public_holidays)
    }
    
    return result


def should_use_v2(input_json: Dict[str, Any], validate: bool = True) -> Tuple[bool, str, Optional[DailyHeadcountValidation]]:
    """
    Determine if v2 processing should be used and optionally validate.
    
    This is the main entry point for auto-detection logic.
    
    Args:
        input_json: The solver input JSON
        validate: Whether to run validation on dailyHeadcount
        
    Returns:
        Tuple of (use_v2, reason, validation_result)
    """
    api_version, has_daily_headcount, detection_info = detect_api_version(input_json)
    
    validation_result = None
    if has_daily_headcount and validate:
        validation_result = validate_daily_headcount(input_json)
        
        if not validation_result.is_valid:
            logger.warning(
                f"dailyHeadcount validation failed: {len(validation_result.errors)} errors. "
                "Proceeding with v2 but solver may fail."
            )
    
    use_v2 = (api_version == "v2" or has_daily_headcount)
    reason = detection_info["detection_reason"]
    
    if use_v2:
        logger.info(f"[version_detector] Auto-routing to v2: {reason}")
    else:
        logger.debug(f"[version_detector] Using v1: {reason}")
    
    return use_v2, reason, validation_result
