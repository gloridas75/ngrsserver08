"""
v2 Solve Router - Enhanced API with dailyHeadcount support.

This module provides the v2 solve endpoints that support:
- dailyHeadcount array for variable staffing per day
- dayType field for day classification (Normal, PublicHoliday, EveOfPH)
- Enhanced output with dailyCoverage summary

Only applies to demandBased rostering mode.
"""

import os
import json
import uuid
import time
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, File, UploadFile
from fastapi.responses import ORJSONResponse

from context.engine.data_loader import load_input
from context.engine.solver_engine import solve
from context.engine.slot_builder_v2 import build_slots_v2
from src.models import (
    SolveRequest, AsyncJobRequest, AsyncJobResponse, JobStatusResponse
)
from src.output_builder import build_output
from src.redis_job_manager import RedisJobManager
from src.feasibility_checker import quick_feasibility_check
from src.offset_manager import ensure_staggered_offsets
from src.input_validator import validate_input

logger = logging.getLogger("ngrs.api.v2")

router = APIRouter()

# Initialize Redis job manager
job_manager = RedisJobManager(
    result_ttl_seconds=int(os.getenv("RESULT_TTL_SECONDS", "3600")),
    key_prefix=os.getenv("REDIS_KEY_PREFIX", "ngrs")
)


async def load_json_from_upload(file: UploadFile) -> dict:
    """Load and parse JSON from uploaded file."""
    try:
        raw = await file.read()
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Unable to parse uploaded file as JSON: {str(e)}"
        )


def get_input_json(request_obj: Optional[SolveRequest], uploaded_file_json: Optional[dict], 
                   raw_body_json: Optional[dict] = None) -> tuple:
    """Select input JSON from body or file."""
    warnings = []
    input_json = None
    source = None
    
    if request_obj and request_obj.input_json:
        input_json = request_obj.input_json
        source = "body (wrapped)"
    elif raw_body_json and "input_json" in raw_body_json:
        input_json = raw_body_json["input_json"]
        source = "body (wrapped)"
    elif raw_body_json and ("schemaVersion" in raw_body_json or "planningHorizon" in raw_body_json):
        input_json = raw_body_json
        source = "body (raw NGRS input)"
    elif uploaded_file_json:
        input_json = uploaded_file_json
        source = "uploaded file"
    
    if input_json is None:
        raise HTTPException(
            status_code=400,
            detail="Provide either input_json in request body or upload a JSON file."
        )
    
    return input_json, warnings


def build_daily_coverage_summary(slots: List[Any], assignments: List[Dict]) -> List[Dict]:
    """
    Build dailyCoverage summary showing target vs actual headcount per day.
    
    Args:
        slots: List of Slot objects with _dayType attribute
        assignments: List of assignment dicts from output
        
    Returns:
        List of daily coverage entries
    """
    # Build target headcount from slots
    target_by_key = {}  # (date, shiftCode) -> {headcount, dayType}
    for slot in slots:
        key = (slot.date.isoformat(), slot.shiftCode)
        if key not in target_by_key:
            day_type = getattr(slot, '_dayType', 'Normal')
            target_by_key[key] = {'headcount': 0, 'dayType': day_type}
        target_by_key[key]['headcount'] += 1
    
    # Build assigned count from assignments
    assigned_by_key = {}  # (date, shiftCode) -> count
    for asgn in assignments:
        if asgn.get('status') == 'ASSIGNED':
            key = (asgn.get('date'), asgn.get('shiftCode'))
            assigned_by_key[key] = assigned_by_key.get(key, 0) + 1
    
    # Build coverage summary
    coverage = []
    for key in sorted(target_by_key.keys()):
        date_str, shift_code = key
        target = target_by_key[key]['headcount']
        day_type = target_by_key[key]['dayType']
        assigned = assigned_by_key.get(key, 0)
        
        coverage.append({
            'date': date_str,
            'shiftCode': shift_code,
            'dayType': day_type,
            'targetHeadcount': target,
            'assignedCount': assigned,
            'coverageRate': round((assigned / target * 100), 1) if target > 0 else 0.0
        })
    
    return coverage


def enrich_assignments_with_daytype(assignments: List[Dict], slots: List[Any]) -> List[Dict]:
    """
    Add dayType to assignments based on slot metadata.
    
    Args:
        assignments: List of assignment dicts
        slots: List of Slot objects with _dayType attribute
        
    Returns:
        Assignments with dayType field added
    """
    # Build slot lookup
    slot_lookup = {}
    for slot in slots:
        slot_lookup[slot.slot_id] = slot
    
    for asgn in assignments:
        slot_id = asgn.get('slotId')
        if slot_id and slot_id in slot_lookup:
            slot = slot_lookup[slot_id]
            asgn['dayType'] = getattr(slot, '_dayType', 'Normal')
        else:
            # Infer from date if slot not found
            asgn['dayType'] = 'Normal'
    
    return assignments


@router.post("/solve", response_class=ORJSONResponse)
async def solve_sync_v2(
    request: Request,
    file: Optional[UploadFile] = File(None),
    payload: Optional[SolveRequest] = None
):
    """
    v2 Synchronous Solve - Supports dailyHeadcount for variable staffing.
    
    This endpoint supports the enhanced input schema with:
    - dailyHeadcount: Array of {date, shiftCode, headcount, dayType}
    - Variable slots per day based on dailyHeadcount
    - dayType in output assignments
    - dailyCoverage summary in output
    
    Only applies to demandBased rostering mode.
    For outcomeBased, behavior is same as v1.
    
    **Input Schema (v0.98+):**
    ```json
    {
      "requirements": [{
        "requirementId": "346_1",
        "headcount": 5,
        "dailyHeadcount": [
          {"date": "2026-02-01", "shiftCode": "D", "headcount": 5, "dayType": "Normal"},
          {"date": "2026-02-17", "shiftCode": "D", "headcount": 3, "dayType": "PublicHoliday"}
        ]
      }]
    }
    ```
    
    **Output Enhancements:**
    - assignments[].dayType: "Normal" | "PublicHoliday" | "EveOfPH"
    - dailyCoverage: Summary of target vs actual headcount per day
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    start_time = time.perf_counter()
    
    try:
        # Parse input
        raw_body_json = None
        if request.headers.get("content-type", "").startswith("application/json"):
            try:
                raw_body = await request.body()
                if raw_body:
                    raw_body_json = json.loads(raw_body)
            except Exception:
                raw_body_json = None
        
        uploaded_json = None
        if file:
            uploaded_json = await load_json_from_upload(file)
        
        input_json, warnings = get_input_json(payload, uploaded_json, raw_body_json)
        
        # Ensure staggered offsets
        input_json = ensure_staggered_offsets(input_json)
        
        # Mark as v2 API
        input_json['_apiVersion'] = 'v2'
        
        # Load context
        ctx = load_input(input_json)
        
        # Check if this is demandBased with dailyHeadcount
        rostering_basis = ctx.get('_rosteringBasis', 'demandBased')
        has_daily_headcount = False
        
        for dmd in input_json.get('demandItems', []):
            for req in dmd.get('requirements', []):
                if req.get('dailyHeadcount'):
                    has_daily_headcount = True
                    break
        
        # Use v2 slot builder if demandBased with dailyHeadcount
        if rostering_basis == 'demandBased' and has_daily_headcount:
            logger.info(f"[v2] Using v2 slot builder with dailyHeadcount support")
            slots = build_slots_v2(ctx)
            ctx['slots'] = slots
            ctx['_usedV2SlotBuilder'] = True
        else:
            logger.info(f"[v2] Using standard slot builder (no dailyHeadcount)")
            ctx['_usedV2SlotBuilder'] = False
        
        # Solve
        result = solve(ctx)
        
        # Build output
        output = build_output(ctx, result, input_json)
        
        # v2 enhancements: Add dayType and dailyCoverage
        if ctx.get('_usedV2SlotBuilder') and ctx.get('slots'):
            # Add dayType to assignments
            if 'assignments' in output:
                output['assignments'] = enrich_assignments_with_daytype(
                    output['assignments'], 
                    ctx['slots']
                )
            
            # Add dailyCoverage summary
            output['dailyCoverage'] = build_daily_coverage_summary(
                ctx['slots'],
                output.get('assignments', [])
            )
        
        # Add v2 metadata
        output['meta'] = output.get('meta', {})
        output['meta']['apiVersion'] = 'v2'
        output['meta']['usedDailyHeadcount'] = has_daily_headcount
        
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info(f"v2_solve requestId={request_id} status={result.get('status')} "
                   f"dailyHeadcount={has_daily_headcount} durMs={elapsed_ms}")
        
        return output
        
    except Exception as e:
        logger.error(f"v2_solve error requestId={request_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/solve/async", response_model=AsyncJobResponse)
async def solve_async_v2(
    request: Request,
    payload: Optional[AsyncJobRequest] = None
):
    """
    v2 Asynchronous Solve - Submit job with dailyHeadcount support.
    
    Supports variable daily headcount for demand-based rostering.
    Output will include dayType and dailyCoverage when dailyHeadcount is used.
    
    **Input Schema (v0.98+):**
    - dailyHeadcount: Array per requirement
    - dayType: "Normal", "PublicHoliday", "EveOfPH"
    
    **Output Enhancements:**
    - assignments[].dayType
    - dailyCoverage summary
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    
    try:
        # Parse raw body
        raw_body_json = None
        if request.headers.get("content-type", "").startswith("application/json"):
            try:
                raw_body = await request.body()
                if raw_body:
                    raw_body_json = json.loads(raw_body)
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid JSON: {str(e)}"
                )
        
        input_json, warnings = get_input_json(
            request_obj=payload,
            uploaded_file_json=None,
            raw_body_json=raw_body_json
        )
        
        # Extract optional parameters
        priority = 0
        webhook_url = None
        
        if payload:
            priority = payload.priority or 0
            webhook_url = payload.webhook_url
        elif raw_body_json:
            priority = raw_body_json.get("priority", 0)
            webhook_url = raw_body_json.get("webhook_url")
        
        # Validate input
        validation_result = validate_input(input_json)
        if not validation_result.is_valid:
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "validation_failed",
                    "message": "Input validation failed.",
                    **validation_result.to_dict()
                }
            )
        
        # Check for dailyHeadcount
        has_daily_headcount = False
        for dmd in input_json.get('demandItems', []):
            for req in dmd.get('requirements', []):
                if req.get('dailyHeadcount'):
                    has_daily_headcount = True
                    break
        
        # Quick feasibility check
        feasibility_result = None
        try:
            feasibility_result = quick_feasibility_check(input_json)
        except Exception as check_error:
            logger.warning(f"Feasibility check failed: {check_error}")
        
        # Mark as v2 for worker to use v2 slot builder
        input_json['_apiVersion'] = 'v2'
        input_json['_hasDailyHeadcount'] = has_daily_headcount
        
        # Create job
        job_id = job_manager.create_job(input_json, webhook_url=webhook_url)
        
        logger.info(f"v2_async_job_created requestId={request_id} jobId={job_id} "
                   f"dailyHeadcount={has_daily_headcount}")
        
        return AsyncJobResponse(
            job_id=job_id,
            status="queued",
            created_at=datetime.now().isoformat(),
            message=f"Job submitted successfully (v2 API, dailyHeadcount={has_daily_headcount})",
            feasibility_check=feasibility_result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"v2_async_job_error requestId={request_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create job: {str(e)}")


@router.get("/solve/async/{job_id}", response_model=JobStatusResponse)
async def get_job_status_v2(job_id: str):
    """Get status of asynchronous solver job (v2)."""
    job_info = job_manager.get_job(job_id)
    
    if not job_info:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    return JobStatusResponse(
        job_id=job_info.job_id,
        status=job_info.status.value,
        created_at=datetime.fromtimestamp(job_info.created_at).isoformat(),
        started_at=datetime.fromtimestamp(job_info.started_at).isoformat() if job_info.started_at else None,
        completed_at=datetime.fromtimestamp(job_info.completed_at).isoformat() if job_info.completed_at else None,
        error_message=job_info.error_message,
        result_available=(job_info.status.value == "completed"),
        result_size_bytes=job_info.result_size_bytes
    )


@router.get("/solve/async/{job_id}/result")
async def get_job_result_v2(job_id: str):
    """Download result of completed solver job (v2)."""
    job_info = job_manager.get_job(job_id)
    
    if not job_info:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    if job_info.status.value == "failed":
        raise HTTPException(status_code=410, detail=f"Job failed: {job_info.error_message}")
    
    if job_info.status.value == "expired":
        raise HTTPException(status_code=410, detail="Job result expired")
    
    if job_info.status.value != "completed":
        raise HTTPException(status_code=425, detail=f"Job not completed (status: {job_info.status.value})")
    
    result = job_manager.get_result(job_id)
    
    if not result:
        raise HTTPException(status_code=410, detail="Result no longer available")
    
    return ORJSONResponse(content=result)
