# Quick Start Guide

## 🌐 Production API

**Production URL**: [https://ngrssolver09.comcentricapps.com](https://ngrssolver09.comcentricapps.com)  
**Infrastructure**: Ubuntu 22.04 EC2 (AWS) - NOT App Runner  
**API Base**: `https://ngrssolver09.comcentricapps.com`

### Quick Test
```bash
# Check production status
curl https://ngrssolver09.comcentricapps.com/health

# Submit async job
curl -X POST https://ngrssolver09.comcentricapps.com/solve/async \
  -H "Content-Type: application/json" \
  -d @your_input.json
```

---

## Running the Solver Locally

### Option 1: Auto-generated Timestamp Filename (Recommended)
Generates filename with pattern `output_DDMM_HHmm.json`

```bash
# Using Python directly
python src/run_solver.py --in input_enhanced.json

# Using Make
make solve-auto

# Result: output/output_1211_1335.json (example: Dec 11, 13:35)
```

### Option 2: Explicit Output Filename
Specify exactly what you want to name the output file

```bash
# Using Python directly
python src/run_solver.py --in input_enhanced.json --out output_my_results.json

# Using Make
make solve

# Result: output/output_my_results.json
```

### Options Explained

| Option | Description |
|--------|-------------|
| `--in <file>` | Input JSON file (looks in `input/` folder automatically) |
| `--out <file>` | **Optional** output filename. If omitted, auto-generates with timestamp |
| `--time <secs>` | Solver time limit in seconds (default: 15) |

## Viewing Results

### Start the Server
```bash
./start_viewer.sh
# or
python server.py
# or
make server
```

### Open in Browser
```
http://localhost:8000/viewer.html
```

### Using the Viewer
1. Server automatically lists all JSON files from the `output/` folder
2. Select any file from the dropdown
3. View interactive dashboards:
   - 📈 Summary statistics
   - 👥 Assignments
   - 👤 Employee details
   - ⚠️ Violations analysis
   - 📅 Timeline
   - ℹ️ Metadata

## File Organization

```
📁 ngrssolver/
├── 📁 input/              ← Input files go here
│   ├── input_enhanced.json
│   ├── input_realistic.json
│   └── ...
├── 📁 output/             ← Output files go here
│   ├── output_1211_1335.json  (auto-generated)
│   ├── output_1211_1340.json  (auto-generated)
│   ├── output_my_results.json (explicit)
│   └── ...
├── viewer.html            ← Open this in browser
├── server.py              ← Run this for file browsing
└── src/
    └── run_solver.py      ← Main solver script
```

## Common Workflows

### Workflow 1: Quick Test with Auto-Timestamp
```bash
# Run solver
make solve-auto

# Start viewer
make server

# Open browser to http://localhost:8000/viewer.html
# Select the latest output file from dropdown
```

### Workflow 2: Named Output for Comparison
```bash
# Run multiple tests with explicit names
python src/run_solver.py --in input_enhanced.json --out test_v1.json
python src/run_solver.py --in input_realistic.json --out test_v2.json

# Compare results in viewer
```

### Workflow 3: Production Run with Auto-Timestamp
```bash
# Just run without --out flag
python src/run_solver.py --in input_enhanced.json

# Automatic filename: output/output_DDMM_HHMM.json
# Makes it easy to track when each run was performed
```

## Tips

✅ **Use auto-timestamp** when you're testing multiple configurations  
✅ **Use explicit names** when you want to keep specific versions  
✅ **File server must be running** to use the interactive viewer  
✅ **All files go to `output/`** - no cluttering root directory  
✅ **Input files stay in `input/`** - organized and separate
