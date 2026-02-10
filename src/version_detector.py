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


def _is_valid_time_format(time_str: str) -> bool:
    """
    Validate time string format (HH:MM or HH:MM:SS).
    
    Args:
        time_str: Time string to validate
        
    Returns:
        True if valid format, False otherwise
    """
    import re
    
    if not time_str or not isinstance(time_str, str):
        return False
    
    # Match HH:MM or HH:MM:SS format
    pattern = r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9](:[0-5][0-9])?$'
    return bool(re.match(pattern, time_str))


def detect_api_version(input_json: Dict[str, Any]) -> Tuple[str, bool, Dict[str, Any]]:
    """
    Detect which API version to use based on input features.
    
    Auto-detection rules:
    1. If explicit 'apiVersion' field is present, use it
    2. If any requirement has 'dailyHeadcount' array, use v2
    3. If any requirement has 'productTypeIds' array, use v2
    4. If any dailyHeadcount entry has time overrides, use v2
    5. Otherwise, use v1 (backward compatible)
    
    Args:
        input_json: The solver input JSON
        
    Returns:
        Tuple of (api_version, has_v2_features, detection_info)
        - api_version: "v1" or "v2"
        - has_v2_features: True if any v2 feature is present
        - detection_info: Dict with detection details
    """
    detection_info = {
        "explicit_version": None,
        "has_daily_headcount": False,
        "has_product_type_ids": False,
        "has_time_overrides": False,
        "daily_headcount_count": 0,
        "requirements_with_daily_hc": 0,
        "requirements_with_product_type_ids": 0,
        "entries_with_time_overrides": 0,
        "detection_reason": "",
        "v2_features": []
    }
    
    # Check for explicit apiVersion field
    explicit_version = input_json.get("apiVersion")
    if explicit_version:
        detection_info["explicit_version"] = explicit_version
        detection_info["detection_reason"] = f"Explicit apiVersion={explicit_version} in input"
        return explicit_version, False, detection_info
    
    # Check for v2 features in requirements
    has_daily_headcount = False
    has_product_type_ids = False
    has_time_overrides = False
    total_daily_hc_entries = 0
    requirements_with_daily_hc = 0
    requirements_with_product_type_ids = 0
    entries_with_time_overrides = 0
    v2_features = []
    
    for dmd in input_json.get("demandItems", []):
        for req in dmd.get("requirements", []):
            # Check for dailyHeadcount
            daily_hc = req.get("dailyHeadcount", [])
            if daily_hc and isinstance(daily_hc, list) and len(daily_hc) > 0:
                has_daily_headcount = True
                requirements_with_daily_hc += 1
                total_daily_hc_entries += len(daily_hc)
                
                # Check for time overrides within dailyHeadcount entries
                for entry in daily_hc:
                    if entry.get("startTimeOverride") or entry.get("endTimeOverride"):
                        has_time_overrides = True
                        entries_with_time_overrides += 1
            
            # Check for productTypeIds array (v2 OR logic)
            product_type_ids = req.get("productTypeIds", [])
            if product_type_ids and isinstance(product_type_ids, list) and len(product_type_ids) > 0:
                has_product_type_ids = True
                requirements_with_product_type_ids += 1
    
    # Build detection info
    detection_info["has_daily_headcount"] = has_daily_headcount
    detection_info["has_product_type_ids"] = has_product_type_ids
    detection_info["has_time_overrides"] = has_time_overrides
    detection_info["daily_headcount_count"] = total_daily_hc_entries
    detection_info["requirements_with_daily_hc"] = requirements_with_daily_hc
    detection_info["requirements_with_product_type_ids"] = requirements_with_product_type_ids
    detection_info["entries_with_time_overrides"] = entries_with_time_overrides
    
    # Build v2 features list
    if has_daily_headcount:
        v2_features.append(f"dailyHeadcount ({total_daily_hc_entries} entries)")
    if has_product_type_ids:
        v2_features.append(f"productTypeIds ({requirements_with_product_type_ids} requirements)")
    if has_time_overrides:
        v2_features.append(f"timeOverrides ({entries_with_time_overrides} entries)")
    
    detection_info["v2_features"] = v2_features
    
    # Determine if v2 should be used
    has_v2_features = has_daily_headcount or has_product_type_ids or has_time_overrides
    
    if has_v2_features:
        detection_info["detection_reason"] = f"Auto-detected v2: {', '.join(v2_features)}"
        return "v2", True, detection_info
    else:
        detection_info["detection_reason"] = "No v2 features found, using v1"
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
    entries_with_time_overrides = 0
    requirements_with_product_type_ids = 0
    
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
                
                # === v2 VALIDATION: Validate time overrides ===
                start_time_override = entry.get("startTimeOverride")
                end_time_override = entry.get("endTimeOverride")
                
                # Track time overrides for summary
                if start_time_override or end_time_override:
                    entries_with_time_overrides += 1
                
                if start_time_override:
                    if not _is_valid_time_format(start_time_override):
                        result.add_error(
                            "INVALID_TIME_OVERRIDE",
                            f"Invalid startTimeOverride format: '{start_time_override}'. Expected HH:MM or HH:MM:SS",
                            f"{field_prefix}.startTimeOverride",
                            {"value": start_time_override}
                        )
                
                if end_time_override:
                    if not _is_valid_time_format(end_time_override):
                        result.add_error(
                            "INVALID_TIME_OVERRIDE",
                            f"Invalid endTimeOverride format: '{end_time_override}'. Expected HH:MM or HH:MM:SS",
                            f"{field_prefix}.endTimeOverride",
                            {"value": end_time_override}
                        )
                
                # Warn if only one override is present (unusual but allowed)
                if (start_time_override and not end_time_override) or (end_time_override and not start_time_override):
                    result.add_warning(
                        "PARTIAL_TIME_OVERRIDE",
                        f"Only one time override specified. Missing: {'endTimeOverride' if start_time_override else 'startTimeOverride'}. "
                        f"The other time will use default from shiftDetails.",
                        f"{field_prefix}",
                        {"startTimeOverride": start_time_override, "endTimeOverride": end_time_override}
                    )
            
            # === v2 VALIDATION: Validate productTypeIds ===
            product_type_ids = req.get("productTypeIds", [])
            if product_type_ids:
                if not isinstance(product_type_ids, list):
                    result.add_error(
                        "INVALID_PRODUCT_TYPE_IDS",
                        f"productTypeIds must be an array, got: {type(product_type_ids).__name__}",
                        f"demandItems[{dmd_idx}].requirements[{req_idx}].productTypeIds"
                    )
                else:
                    for pt_idx, pt_id in enumerate(product_type_ids):
                        if not isinstance(pt_id, str) or not pt_id.strip():
                            result.add_error(
                                "INVALID_PRODUCT_TYPE_ID",
                                f"productTypeIds[{pt_idx}] must be a non-empty string, got: {pt_id}",
                                f"demandItems[{dmd_idx}].requirements[{req_idx}].productTypeIds[{pt_idx}]"
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
            
            # Track productTypeIds for summary
            if req.get("productTypeIds"):
                requirements_with_product_type_ids += 1
    
    # Build summary
    result.summary = {
        "requirementsWithDailyHeadcount": total_requirements_with_dhc,
        "totalEntries": total_entries,
        "datesWithCoverage": len(dates_covered),
        "planningHorizonDays": (end_date - start_date).days + 1,
        "publicHolidaysCount": len(public_holidays),
        "entriesWithTimeOverrides": entries_with_time_overrides,
        "requirementsWithProductTypeIds": requirements_with_product_type_ids
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
