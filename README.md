# NGRS Solver v0.8

**Next-Generation Roster Scheduling Solver** - An intelligent shift scheduling optimizer powered by Google OR-Tools CP-SAT solver with REST API and Redis-based async job processing.

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![OR-Tools](https://img.shields.io/badge/OR--Tools-9.11-green.svg)](https://developers.google.com/optimization)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-teal.svg)](https://fastapi.tiangolo.com/)
[![Redis](https://img.shields.io/badge/Redis-7.0-red.svg)](https://redis.io/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)]()

---

## 🚀 Features

### Core Solver
- **CP-SAT Optimization Engine** - Google OR-Tools constraint programming solver
- **14/15 Hard Constraints Implemented** - MOM compliance, rest periods, licenses, gender balance, etc.
- **Intelligent Rotation Patterns** - Automatic offset optimization for fair work distribution
- **Multi-Shift Support** - Day/Night/Evening shifts with flexible timings
- **Real-time Validation** - Pre-solve constraint checking and post-solve verification

### REST API
- **FastAPI Framework** - High-performance async REST API
- **Synchronous & Asynchronous Modes** - Immediate response or background processing
- **Three Main Endpoints**:
  - `/solve` - Synchronous solver (immediate response)
  - `/solve/async` - Asynchronous job submission (returns job UUID)
  - `/configure` - Get optimal work patterns and staffing recommendations (ICPMP tool)
- **Multiple Input Methods** - JSON body or file upload
- **Request Tracking** - UUID-based request tracing
- **Comprehensive Logging** - Performance metrics and error tracking

### Async Job Processing (NEW in v0.8)
- **Redis-Backed Queue** - Distributed job queue for scalability
- **Multi-Worker Architecture** - Process multiple jobs concurrently
- **Job Status Tracking** - Real-time status updates (queued, in_progress, completed, failed)
- **Result Caching** - Results stored with TTL for retrieval
- **Horizontal Scaling** - Workers can run on separate machines
- **Auto-Deployment** - GitHub Actions CI/CD to EC2

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
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│                  Solver Engine Layer                     │
│  context/engine/solver_engine.py                        │
│  - Data loading, constraint building, optimization      │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│               OR-Tools CP-SAT Solver                     │
│  Google OR-Tools 9.11.4210                              │
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

| Metric | Value |
|--------|-------|
| **Solve Time** | 150-500ms (30-day roster, 8 employees) |
| **Configuration Time** | <5ms (2-5 requirements) |
| **API Response** | 180-200ms (including JSON serialization) |
| **Scalability** | Tested up to 50+ requirements, 100+ employees |
| **Success Rate** | 100% (OPTIMAL status on all test scenarios) |

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
- **OR-Tools** 9.11.4210 (via optfold-py-0.4.2)
- **FastAPI** 0.115.14
- **Uvicorn** 0.34.3
- **Pydantic** 2.10.3
- **orjson** 3.10.13

See [requirements.txt](requirements.txt) for complete list.

---

## 🤝 Integration Workflow

```
Step 1: Configuration       Step 2: Review           Step 3: Roster
Optimization                & Hire                   Generation
     ↓                           ↓                        ↓
POST /configure         Review recommendations    POST /solve
→ Get patterns          → Hire 7 employees        → Generate roster
→ Get staffing needs    → Validate coverage       → Get assignments
```

---

## 📄 License

Proprietary - All rights reserved

---

## 👤 Author

**G Anthony**  
Repository: https://github.com/gloridas75/ngrssolver0.7

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

**Last Updated**: November 23, 2025  
**Version**: 0.7  
**Status**: Production Ready ✅
