"""
Simple ICPMP v3 Test Server (without Redis dependencies)

Runs just the ICPMP endpoints for local testing.
"""

import sys
import json
import logging
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import ORJSONResponse
from fastapi.middleware.cors import CORSMiddleware
import time

# Setup path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from context.engine.config_optimizer_v3 import optimize_multiple_requirements

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ICPMP v3 Test Server")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "3.0-test"}


@app.post("/icpmp", response_class=ORJSONResponse)
async def icpmp_calculate(request: Request):
    """v1.0 Simple calculator"""
    start_time = time.perf_counter()
    
    try:
        data = await request.json()
        headcount = data.get('headcount')
        work_pattern = data.get('workPattern')
        
        if not headcount or not work_pattern:
            raise HTTPException(status_code=400, detail="Missing headcount or workPattern")
        
        cycle_length = len(work_pattern)
        work_days = sum(1 for shift in work_pattern if shift != 'O')
        
        if work_days == 0:
            raise HTTPException(status_code=400, detail="Pattern must have at least one work day")
        
        unique_shifts = set(shift for shift in work_pattern if shift != 'O')
        unique_shift_count = len(unique_shifts)
        
        slots_per_work_day = headcount * unique_shift_count
        employees_needed = int(unique_shift_count * headcount * (cycle_length / work_days))
        
        formula = f"{unique_shift_count} shifts × {headcount} headcount × ({cycle_length} cycle / {work_days} work days) = {employees_needed}"
        
        result = {
            "employeesNeeded": employees_needed,
            "cycleLength": cycle_length,
            "workDays": work_days,
            "uniqueShiftCodes": unique_shift_count,
            "shiftTypes": list(unique_shifts),
            "slotsPerWorkDay": slots_per_work_day,
            "formula": formula,
            "workPattern": work_pattern
        }
        
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info(f"ICPMP v1: HC={headcount} pattern={'-'.join(work_pattern)} → {employees_needed} employees ({elapsed_ms}ms)")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ICPMP v1 error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/icpmp/v3", response_class=ORJSONResponse)
async def icpmp_v3_calculate(request: Request):
    """v3.0 Optimal calculator with U-slots"""
    start_time = time.perf_counter()
    
    try:
        data = await request.json()
        
        planning_horizon = data.get('planningHorizon')
        demand_items = data.get('demandItems')
        
        if not planning_horizon or not demand_items:
            raise HTTPException(status_code=400, detail="Missing planningHorizon or demandItems")
        
        public_holidays = data.get('publicHolidays', [])
        coverage_days = data.get('coverageDays')
        
        # Flatten requirements
        all_requirements = []
        for demand_item in demand_items:
            demand_item_id = demand_item.get('demandItemId', 'unknown')
            requirements = demand_item.get('requirements', [])
            
            for req in requirements:
                req_with_context = req.copy()
                req_with_context['demandItemId'] = demand_item_id
                
                if 'requirementId' not in req_with_context:
                    req_with_context['requirementId'] = f"{demand_item_id}_{len(all_requirements) + 1}"
                
                all_requirements.append(req_with_context)
        
        if not all_requirements:
            raise HTTPException(status_code=400, detail="No requirements found")
        
        logger.info(f"ICPMP v3: Processing {len(all_requirements)} requirements")
        
        # Calculate optimal employees
        results = optimize_multiple_requirements(
            requirements=all_requirements,
            planning_horizon=planning_horizon,
            public_holidays=public_holidays,
            coverage_days=coverage_days
        )
        
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        
        response = {
            "version": "3.0",
            "algorithm": "U_SLOT_INJECTION",
            "optimality": "PROVEN_MINIMAL",
            "planningHorizon": planning_horizon,
            "publicHolidays": public_holidays,
            "coverageDays": coverage_days,
            "results": results,
            "summary": {
                "totalRequirements": len(all_requirements),
                "successfulCalculations": sum(1 for r in results if 'error' not in r),
                "failedCalculations": sum(1 for r in results if 'error' in r),
                "totalEmployeesRequired": sum(
                    r['configuration']['employeesRequired'] 
                    for r in results if 'configuration' in r
                ),
                "computationTimeMs": elapsed_ms
            }
        }
        
        logger.info(f"ICPMP v3: Completed in {elapsed_ms}ms - {response['summary']['totalEmployeesRequired']} total employees")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ICPMP v3 error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting ICPMP v3 Test Server...")
    print("   📍 http://localhost:8080")
    print("   📄 Open ICPMP.html in browser (set USE_LOCAL=true)")
    print("")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
