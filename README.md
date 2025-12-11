# NGRS Solver v0.95

**Next-Generation Roster Scheduling Solver** - An intelligent shift scheduling optimizer powered by Google OR-Tools CP-SAT solver with REST API and Redis-based async job processing.

🌐 **Production**: [https://ngrssolver09.comcentricapps.com](https://ngrssolver09.comcentricapps.com)  
🖥️ **Infrastructure**: Ubuntu 22.04 EC2 (AWS) with Docker, Redis, and systemd service

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![OR-Tools](https://img.shields.io/badge/OR--Tools-9.11-green.svg)](https://developers.google.com/optimization)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-teal.svg)](https://fastapi.tiangolo.com/)
[![Redis](https://img.shields.io/badge/Redis-7.0-red.svg)](https://redis.io/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)]()

---

## 🆕 What's New in v0.95 (December 2025)

### 🎯 Per-Requirement Auto-Optimization
**Intelligent ratio optimization at requirement level!**
- Configure auto-optimization per work pattern
- Different patterns can have different optimization strategies
- Optional optimization (only runs when explicitly enabled)
- Better control and flexibility for production scenarios

### 💾 Automatic Ratio Caching
**91% time savings on repeated patterns!**
- Automatically caches optimal strictAdherenceRatio values
- Pattern-based intelligent caching
- Reuses optimal ratios for same patterns
- Reduces solve time from 45 min to 15 min for large rosters

### ⚙️ Configurable Optimization Range
**Flexible ratio testing for different scales!**
- Customize min/max strict ratio and step size
- Test 3-11 ratios based on your needs
- Production-optimized defaults (60%-80%, step 10%)
- Reduces optimization time by 64-73%

---

## What's New in v0.8 (November 2025)

### 🔔 Webhook Notifications
**Stop polling!** Get instant HTTP POST notifications when jobs complete.
- Automatic callbacks on completion, failure, or cancellation
- No more repeated status checks
- Works with webhook.site or your custom endpoint

### ⚡ Quick Feasibility Pre-Check
**Save 10 minutes per infeasible job!** Fast validation (<100ms) before solver runs.
- Employee count estimation
- Role/rank/gender/scheme matching analysis
- Work pattern feasibility check
- Actionable warnings and recommendations

### 🛑 Job Cancellation
**Stop expensive solver runs gracefully!**
- Cancel queued jobs instantly
- Stop running jobs within 30-60 seconds
- Clean up completed results
- Two endpoints: DELETE and POST

### 📅 ISO Timestamps
**Human-readable timestamps everywhere!**
- `2025-11-26T14:30:15.123456` instead of `1732611015.123456`
- Easy to read, compare, and sort
- Microsecond precision

### 🧹 Automatic Cleanup (TTL)
**No more manual maintenance!**
- Jobs auto-expire after 1 hour
- Redis memory stays clean
- Improved performance

### 🚀 CP-SAT Parallelization
**2-3x faster solving for large problems!**
- Multi-threaded search (1-16 workers)
- Adaptive thread allocation based on problem size
- Optional manual override via `CPSAT_NUM_THREADS` env var
- No changes to input/output formats

---

## 🚀 Features

### Core Solver
- **CP-SAT Optimization Engine** - Google OR-Tools constraint programming solver with **multi-threading support** 🆕
- **14/15 Hard Constraints Implemented** - MOM compliance, rest periods, licenses, gender balance, etc.
- **Intelligent Rotation Patterns** - Automatic offset optimization for fair work distribution
- **Multi-Shift Support** - Day/Night/Evening shifts with flexible timings
- **Real-time Validation** - Pre-solve constraint checking and post-solve verification
- **Feasibility Pre-Check** - Fast validation (<100ms) before expensive solver runs 🆕

### REST API
- **FastAPI Framework** - High-performance async REST API
- **Synchronous & Asynchronous Modes** - Immediate response or background processing
- **Three Main Endpoints**:
  - `/solve` - Synchronous solver (immediate response)
  - `/solve/async` - Asynchronous job submission with **webhook support** 🆕
  - `/configure` - Get optimal work patterns and staffing recommendations (ICPMP tool)
- **Multiple Input Methods** - JSON body or file upload
- **Request Tracking** - UUID-based request tracing
- **Comprehensive Logging** - Performance metrics and error tracking
- **ISO Timestamps** - Human-readable timestamps in all responses 🆕

### Async Job Processing (Enhanced in v0.8)
- **Redis-Backed Queue** - Distributed job queue for scalability
- **Multi-Worker Architecture** - Process multiple jobs concurrently
- **Job Status Tracking** - Real-time status updates (queued, in_progress, completed, failed, **cancelled** 🆕)
- **Result Caching** - Results stored with **automatic TTL expiration** 🆕
- **Horizontal Scaling** - Workers can run on separate machines
- **Auto-Deployment** - GitHub Actions CI/CD to EC2
- **Webhook Notifications** - Automatic callbacks on job completion 🆕
- **Job Cancellation** - Stop queued or running jobs gracefully 🆕

### Configuration Optimizer (ICPMP Tool)
- **Pre-Planning Intelligence** - Determine staffing needs before hiring
- **Pattern Optimization** - Suggest optimal work patterns (e.g., 4-on-2-off)
- **Coverage Guarantee** - Ensures 100% coverage with minimum staff
- **Fast Response** - Millisecond response time vs. minutes for full solver

---

## 📋 Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/gloridas75/ngrsserver08.git
cd ngrsserver08

# Install dependencies
pip install -r requirements.txt
```

### Run Solver (CLI)

```bash
# Generate roster from input file
python src/run_solver.py --in input/input_v0.7.json

# Output saved to output/output_DDMM_HHMM.json
```

### Run API Server

```bash
# Start FastAPI server
python -m uvicorn src.api_server:app --host 127.0.0.1 --port 8080

# Or use the startup script
bash run_api_server.sh
```

### Test API

```bash
# Health check
curl http://127.0.0.1:8080/health

# Async job submission (NEW: with webhook notification)
curl -X POST http://127.0.0.1:8080/solve/async \
  -H "Content-Type: application/json" \
  -d '{
    "webhook_url": "https://webhook.site/your-unique-url",
    "input_json": {...}
  }'

# Check job status (returns ISO timestamps)
curl http://127.0.0.1:8080/solve/async/{job_id}

# Cancel running job (NEW)
curl -X DELETE http://127.0.0.1:8080/solve/async/{job_id}
# or
curl -X POST http://127.0.0.1:8080/solve/async/{job_id}/cancel

# Configuration optimizer (get staffing recommendations)
curl -X POST http://127.0.0.1:8080/configure \
  -H "Content-Type: application/json" \
  -d @input/config_optimizer_test.json

# Main solver (generate full roster)
curl -X POST http://127.0.0.1:8080/solve \
  -H "Content-Type: application/json" \
  -d @input/input_v0.7.json
```

---

## 📊 Example Output

### Async Job Response (with Feasibility Check) 🆕
```json
{
  "job_id": "abc-123-def-456",
  "status": "QUEUED",
  "message": "Job queued successfully",
  "created_at": "2025-11-26T14:30:15.123456",
  "feasibility_check": {
    "is_feasible": true,
    "summary": "Configuration appears feasible",
    "warnings": [
      "Tight coverage: 15-18 employees needed, 20 available"
    ],
    "recommendations": [
      "Consider adding 2-3 backup employees for flexibility"
    ]
  }
}
```

### Webhook Notification Payload 🆕
```json
{
  "job_id": "abc-123-def-456",
  "status": "COMPLETED",
  "timestamp": "2025-11-26T14:35:22.654321",
  "message": "Job completed successfully"
}
```

### Job Status Response (with ISO Timestamps) 🆕
```json
{
  "job_id": "abc-123-def-456",
  "status": "COMPLETED",
  "created_at": "2025-11-26T14:30:15.123456",
  "updated_at": "2025-11-26T14:35:22.654321",
  "result": {
    "solverRun": {
      "status": "OPTIMAL",
      "wallTimeSeconds": 312.45
    },
    "score": {
      "hard": 0,
      "soft": 15
    }
  }
}
```

### Configuration Optimizer Output
```json
{
  "summary": {
    "totalRequirements": 2,
    "totalEmployees": 7
  },
  "recommendations": [
    {
      "requirementId": "REQ_DAY_GUARD",
      "configuration": {
        "workPattern": ["D", "D", "O", "D", "D", "O"],
        "employeesRequired": 4,
        "rotationOffsets": [0, 1, 2, 3]
      },
      "coverage": {
        "expectedCoverageRate": 100.0
      }
    }
  ]
}
```

### Main Solver Output
```json
{
  "solverRun": {
    "status": "OPTIMAL",
    "wallTimeSeconds": 0.18
  },
  "score": {
    "hard": 0,
    "soft": 0
  },
  "assignments": [
    {
      "employeeId": "EMP001",
      "date": "2024-12-01",
      "demandId": "DEM001",
      "shiftCode": "D",
      "hours": {
        "gross": 12.0,
        "lunch": 1.0,
        "normal": 11.0,
        "ot": 0,
        "paid": 11.0
      }
    }
  ]
}
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     REST API Layer                       │
│  FastAPI Server (src/api_server.py)                     │
│  - /health, /version, /solve, /configure                │
│  - Webhook support, Feasibility checks 🆕               │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│              Redis Job Queue (NEW in v0.8)               │
│  - Job queuing with priority                             │
│  - Result caching with TTL 🆕                           │
│  - Cancellation flags 🆕                                │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│             Worker Pool (Multi-Process)                  │
│  - 2 workers (configurable via SOLVER_WORKERS)           │
│  - Cancellation checkpoint checking 🆕                   │
│  - Webhook notification sending 🆕                       │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│                  Solver Engine Layer                     │
│  context/engine/solver_engine.py                        │
│  - Data loading, constraint building                     │
│  - CP-SAT multi-threading (1-16 workers) 🆕            │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│               OR-Tools CP-SAT Solver                     │
│  Google OR-Tools 9.11.4210                              │
│  - Parallel search exploration 🆕                       │
│  - Constraint satisfaction + optimization                │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│                  Output Builder Layer                    │
│  src/output_builder.py                                  │
│  - JSON formatting, validation, enrichment              │
└─────────────────────────────────────────────────────────┘
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [API_QUICK_REFERENCE.md](API_QUICK_REFERENCE.md) | Quick command reference for API testing |
| [CONFIGURATION_OPTIMIZER_API_TESTING.md](CONFIGURATION_OPTIMIZER_API_TESTING.md) | Full testing guide for ICPMP tool |
| [CONFIGURATION_OPTIMIZER_API_SUMMARY.md](CONFIGURATION_OPTIMIZER_API_SUMMARY.md) | Implementation details and results |
| [API_VALIDATION_SUMMARY.md](API_VALIDATION_SUMMARY.md) | API validation report |
| [implementation_docs/](implementation_docs/) | Complete technical documentation (40+ files) |

---

## 🔧 Constraints Implemented

### Hard Constraints (14/15)
- ✅ **C1** - MOM Daily Hours Cap (Scheme A: 14h, B: 13h, P: 9h)
- ✅ **C2** - MOM Weekly Rest (1 day per 7-day window)
- ✅ **C3** - Consecutive Work Days (max 12 days)
- ✅ **C4** - Rest Period (11h between shifts)
- ✅ **C5** - Off-Day Rules (blackout/whitelist dates)
- ✅ **C6** - Part-Timer Limits (max 4 days/week)
- ✅ **C7** - License Validity (active licenses only)
- ✅ **C8** - Provisional License Validity (PDL expiry)
- ✅ **C9** - Gender Balance (All/Male/Female/Mix enforcement)
- ✅ **C11** - Rank/Product Match (qualification matching)
- ✅ **C12** - Team Completeness (whitelist enforcement)
- ✅ **C15** - Qualification Expiry Override (temporary approvals)
- ✅ **C16** - No Overlap (one assignment per employee per day)
- ✅ **C17** - OT Monthly Cap (max OT hours per month)
- ⏸️ **C10** - Skill/Role Match (deferred - requires input schema enhancement)

### Soft Constraints (Scoring)
Multiple soft constraints for optimizing preferences, rotation patterns, team continuity, etc.

---

## 🎯 Use Cases

### 1. Pre-Planning & Cost Estimation
Use `/configure` endpoint to determine staffing needs and costs before hiring.

### 2. Roster Generation
Use `/solve` endpoint to generate complete day-by-day schedules for 1-3 months.

### 3. What-If Analysis
Test different configurations to find optimal work patterns and coverage.

### 4. Compliance Validation
Ensure all generated rosters comply with MOM regulations and company policies.

---

## 📈 Performance

| Metric | Value | Notes |
|--------|-------|-------|
| **Solve Time** | 150-500ms | 30-day roster, 8 employees |
| **Solve Time (Large)** | 2-5 minutes | 31-day roster, 50+ employees |
| **Parallelization Speedup** | 2-3x | With 8 threads (large problems) 🆕 |
| **Feasibility Check** | <100ms | Pre-solve validation 🆕 |
| **Configuration Time** | <5ms | 2-5 requirements |
| **API Response** | 180-200ms | Including JSON serialization |
| **Job Cancellation** | 30-60s | For running jobs 🆕 |
| **Webhook Latency** | <500ms | HTTP POST notification 🆕 |
| **Scalability** | Tested up to 50+ requirements, 100+ employees |
| **Success Rate** | 100% | OPTIMAL status on all test scenarios |
| **Job TTL** | 1 hour | Automatic cleanup 🆕 |

---

## 🐳 Deployment

### Docker
```bash
# Build image
docker build -t ngrssolver:0.7 .

# Run container
docker run -p 8080:8080 ngrssolver:0.7
```

### AWS App Runner
```bash
# Deploy to App Runner
aws apprunner create-service --cli-input-json file://apprunner.yaml
```

See [implementation_docs/AWS_APPRUNNER_DEPLOYMENT_SUMMARY.md](implementation_docs/AWS_APPRUNNER_DEPLOYMENT_SUMMARY.md) for details.

---

## 📝 Input Schema

```json
{
  "schemaVersion": "0.43",
  "planningHorizon": {
    "startDate": "2024-12-01",
    "endDate": "2024-12-30"
  },
  "publicHolidays": ["2024-12-25"],
  "shifts": [...],
  "employees": [...],
  "demands": [...],
  "constraints": {...}
}
```

See [context/schemas/input.schema.json](context/schemas/input.schema.json) for full specification.

---

## 🧪 Testing

### Run Tests
```bash
# CLI test
python src/run_solver.py --in input/input_v0.7.json

# API test (server must be running)
curl -X POST http://127.0.0.1:8080/solve \
  -d @input/input_v0.7.json | python -m json.tool
```

### Test Files
- `input/input_v0.7.json` - Main test scenario (8 employees, 30 days)
- `input/config_optimizer_test.json` - Configuration optimizer test
- `input/requirements_simple.json` - Simple requirements (5 requirements)
- `input/input_v0.7_C*test.json` - Individual constraint tests

---

## 🔍 Troubleshooting

### API Server Won't Start
```bash
# Check if port 8080 is in use
lsof -i :8080

# Kill existing server
pkill -f "uvicorn.*api_server"
```

### Solver Returns INFEASIBLE
- Check constraint violations in output JSON
- Reduce time limit if solver times out
- Verify input data completeness (employees, demands, shifts)

### View Logs
```bash
tail -f api_server.log
```

---

## 📦 Dependencies

- **Python** 3.12+
- **OR-Tools** 9.11.4210 (via optSolve-py-0.9.0)
- **FastAPI** 0.115.14
- **Uvicorn** 0.34.3
- **Pydantic** 2.10.3
- **orjson** 3.10.13

See [requirements.txt](requirements.txt) for complete list.

---

## 🤝 Integration Workflow

```
Step 1: Configuration       Step 2: Review           Step 3: Async Roster
Optimization                & Hire                   Generation (NEW)
     ↓                           ↓                        ↓
POST /configure         Review recommendations    POST /solve/async
→ Get patterns          → Hire 7 employees        → Submit with webhook 🆕
→ Get staffing needs    → Validate coverage       → Get feasibility check 🆕
                                                   → Receive notification 🆕
                                                   
                                                   Step 4: Monitor & Control
                                                        ↓
                                                   GET /solve/async/stats
                                                   → Check queue status
                                                   → Cancel if needed 🆕
                                                   → Auto-cleanup after 1h 🆕
```

### API Endpoints Summary

| Endpoint | Method | Purpose | New in v0.8 |
|----------|--------|---------|-------------|
| `/health` | GET | Health check | - |
| `/version` | GET | API version | - |
| `/schema` | GET | Input schema | - |
| `/solve` | POST | Synchronous solve | - |
| `/solve/async` | POST | Submit async job | ✅ webhook_url, feasibility |
| `/solve/async/{job_id}` | GET | Get job status | ✅ ISO timestamps |
| `/solve/async/{job_id}` | DELETE | Cancel job | ✅ NEW |
| `/solve/async/{job_id}/cancel` | POST | Cancel job (alt) | ✅ NEW |
| `/solve/async/stats` | GET | Queue statistics | ✅ CANCELLED status |
| `/solve/async/stats?details=true` | GET | Detailed stats | ✅ ISO timestamps |
| `/configure` | POST | ICPMP optimizer | - |
| `/admin/reset` | POST | System reset | - |

---

## 📄 License

Proprietary - All rights reserved

---

## 👤 Author

**G Anthony**  
Repository: https://github.com/gloridas75/ngrssolver0.8

---

## 🆘 Support

For issues, questions, or feature requests, please contact the development team or open an issue in the repository.

---

## 📚 Additional Resources

- [Google OR-Tools Documentation](https://developers.google.com/optimization)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [CP-SAT Primer](https://developers.google.com/optimization/cp/cp_solver)
- [Project Implementation Docs](implementation_docs/)

---

**Last Updated**: November 26, 2025  
**Version**: 0.8  
**Status**: Production Ready ✅

**Recent Changes (v0.8.2):**
- ✅ Webhook notifications for job completion
- ✅ Quick feasibility pre-check (<100ms)
- ✅ Graceful job cancellation
- ✅ ISO timestamps in all responses
- ✅ Automatic job cleanup (TTL)
- ✅ CP-SAT parallelization (2-3x faster)

