"""
v1 Solve Router - Original API endpoints with static headcount.

This module provides the v1 solve endpoints that use static headcount
from requirements. All existing behavior is preserved for backward compatibility.
"""

import os
import json
import uuid
import time
import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, File, UploadFile
from fastapi.responses import ORJSONResponse

from context.engine.data_loader import load_input
from context.engine.solver_engine import solve
from src.models import (
    SolveRequest, AsyncJobRequest, AsyncJobResponse, JobStatusResponse
)
from src.output_builder import build_output
from src.redis_job_manager import RedisJobManager
from src.feasibility_checker import quick_feasibility_check
from src.offset_manager import ensure_staggered_offsets
from src.input_validator import validate_input

logger = logging.getLogger("ngrs.api.v1")

router = APIRouter()

# Initialize Redis job manager (shared with main app)
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
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Error reading uploaded file: {str(e)}"
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
    elif raw_body_json and "input_json" in raw_body_json and isinstance(raw_body_json.get("input_json"), dict):
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
            detail="Provide either input_json in request body, raw NGRS input, or upload a JSON file."
        )
    
    return input_json, warnings


@router.post("/solve", response_class=ORJSONResponse)
async def solve_sync(
    request: Request,
    file: Optional[UploadFile] = File(None),
    payload: Optional[SolveRequest] = None
):
    """
    v1 Synchronous Solve - Uses static headcount from requirements.
    
    This endpoint solves scheduling problems using the original slot creation logic
    where headcount is static across all days in the planning horizon.
    
    For variable daily headcount, use v2 API: POST /v2/solve
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
        
        # Ensure staggered offsets for rotation patterns
        input_json = ensure_staggered_offsets(input_json)
        
        # Load and solve
        ctx = load_input(input_json)
        result = solve(ctx)
        
        # Build output
        output = build_output(ctx, result, input_json)
        
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info(f"v1_solve requestId={request_id} status={result.get('status')} durMs={elapsed_ms}")
        
        return output
        
    except Exception as e:
        logger.error(f"v1_solve error requestId={request_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/solve/async", response_model=AsyncJobResponse)
async def solve_async(
    request: Request,
    payload: Optional[AsyncJobRequest] = None
):
    """
    v1 Asynchronous Solve - Submit job for background processing.
    
    Uses static headcount from requirements. For variable daily headcount,
    use v2 API: POST /v2/solve/async
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
                    detail=f"Invalid JSON in request body: {str(e)}"
                )
        
        input_json, warnings = get_input_json(
            request_obj=payload,
            uploaded_file_json=None,
            raw_body_json=raw_body_json
        )
        
        # Extract optional parameters
        priority = 0
        ttl_seconds = None
        webhook_url = None
        
        if payload:
            priority = payload.priority or 0
            ttl_seconds = payload.ttl_seconds
            webhook_url = payload.webhook_url
        elif raw_body_json:
            priority = raw_body_json.get("priority", 0)
            ttl_seconds = raw_body_json.get("ttl_seconds")
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
        
        # Quick feasibility check
        feasibility_result = None
        try:
            feasibility_result = quick_feasibility_check(input_json)
        except Exception as check_error:
            logger.warning(f"Feasibility check failed: {check_error}")
        
        # Mark as v1 for worker to use correct slot builder
        input_json['_apiVersion'] = 'v1'
        
        # Create job
        job_id = job_manager.create_job(input_json, webhook_url=webhook_url)
        
        logger.info(f"v1_async_job_created requestId={request_id} jobId={job_id}")
        
        return AsyncJobResponse(
            job_id=job_id,
            status="queued",
            created_at=datetime.now().isoformat(),
            message="Job submitted successfully (v1 API)",
            feasibility_check=feasibility_result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"v1_async_job_error requestId={request_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create job: {str(e)}")


@router.get("/solve/async/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Get status of asynchronous solver job."""
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
async def get_job_result(job_id: str):
    """Download result of completed solver job."""
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
