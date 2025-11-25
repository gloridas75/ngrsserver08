# NGRS Solver API - Postman Collection

This folder contains Postman collection and environment files for testing the NGRS Solver API.

## Files

- **NGRS_Solver_API.postman_collection.json** - Complete API collection with all endpoints
- **NGRS_Solver_Local.postman_environment.json** - Environment for local testing
- **NGRS_Solver_Production.postman_environment.json** - Environment for production server

## Recent Updates (v0.7.1 - Nov 25, 2025)

### ICPMP Configuration Optimizer - Schema Changes

#### 1. Shift-Specific Headcount (`headcountPerShift`)

The `/configure` endpoint now uses **`headcountPerShift`** instead of `headcountPerDay` for more precise shift coverage specification.

##### Old Schema (Deprecated)
```json
{
  "requirements": [
    {
      "shiftTypes": ["D", "N"],
      "headcountPerDay": 50  // ❌ Ambiguous
    }
  ]
}
```

##### New Schema (Required)
```json
{
  "requirements": [
    {
      "shiftTypes": ["D", "N"],
      "headcountPerShift": {
        "D": 25,  // ✅ Clear: 25 for Day shift
        "N": 25   // ✅ Clear: 25 for Night shift
      }
    }
  ]
}
```

#### 2. Shift Hour Definitions (`shiftDefinitions`)

**NEW**: You can now specify custom shift hours for accurate calculations. This is especially important for:
- Scheme P shifts (8-hour shifts)
- Non-standard shift durations
- Mixed shift types with different hours

##### Default Behavior (Without shiftDefinitions)
If not provided, all shifts default to **11.0 net hours** (12 gross - 1 lunch):

```json
{
  "requirements": [{"shiftTypes": ["D"], "headcountPerShift": {"D": 4}}],
  "constraints": {"maxWeeklyNormalHours": 44}
}
// D shift assumes 11.0 hours
```

##### Custom Shift Hours (With shiftDefinitions)
For accurate calculations with 8-hour Scheme P shifts:

```json
{
  "shiftDefinitions": {
    "W": {
      "grossHours": 8.0,
      "lunchBreak": 1.0,
      "description": "Wing shift (8h gross, 7h net)"
    },
    "E": {
      "grossHours": 8.0,
      "lunchBreak": 1.0,
      "description": "Evening shift (8h gross, 7h net)"
    }
  },
  "requirements": [
    {
      "shiftTypes": ["W", "E"],
      "headcountPerShift": {"W": 2, "E": 1}
    }
  ]
}
```

##### Comparing 12-Hour vs 8-Hour Shifts
```json
{
  "shiftDefinitions": {
    "D": {"grossHours": 12.0, "lunchBreak": 1.0},  // 11h net
    "P": {"grossHours": 8.0, "lunchBreak": 1.0}    // 7h net
  },
  "requirements": [
    {"id": "REQ_12H", "shiftTypes": ["D"], "headcountPerShift": {"D": 4}},
    {"id": "REQ_8H", "shiftTypes": ["P"], "headcountPerShift": {"P": 4}}
  ]
}
```

**Why this matters**: With `maxWeeklyNormalHours: 44`:
- 12-hour shifts: ~4 days/week → fewer employees needed
- 8-hour shifts: ~5.5 days/week → more employees needed for same coverage

### Response Changes

The API now returns per-shift details:

```json
{
  "configuration": {
    "employeesRequired": 175,
    "employeesRequiredPerShift": {
      "D": 88,
      "N": 87
    }
  },
  "coverage": {
    "requiredPerShift": {
      "D": 25,
      "N": 25
    },
    "requiredPerDay": 50
  }
}
```

## How to Import Updated Collection

### Option 1: Replace Entire Collection (Recommended)

1. **Delete Old Collection** (if exists):
   - In Postman, right-click "NGRS Solver API" collection
   - Select "Delete"
   - Confirm deletion

2. **Import New Collection**:
   - Click "Import" button (top left)
   - Drag `NGRS_Solver_API.postman_collection.json` or click "Choose Files"
   - Click "Import"

3. **Verify Import**:
   - Expand "Configuration Optimizer (ICPMP)" folder
   - Open "Get Optimal Configurations" request
   - Check request body uses `headcountPerShift`

### Option 2: Update Existing Requests Manually

If you have custom modifications you want to keep:

1. **Open Each ICPMP Request**:
   - "Get Optimal Configurations"
   - "ICPMP - Mixed Shift Types"

2. **Update Request Body**:
   - Find `"headcountPerDay": <number>` in each requirement
   - Replace with:
     ```json
     "headcountPerShift": {
       "D": <day_count>,
       "N": <night_count>
     }
     ```
   
3. **Remove Deprecated Fields** (if present):
   - Remove `"shifts": [...]` array (no longer needed)
   - Remove `"optimizationGoals"` (no longer used)

### Option 3: Import as New Collection (Side-by-Side)

If you want to keep both old and new:

1. **Rename Old Collection**:
   - Right-click "NGRS Solver API" → Rename
   - Change to "NGRS Solver API (OLD)"

2. **Import New Collection**:
   - Follow steps in Option 1
   - Both collections will coexist

## Environment Setup

### Local Development

1. Import `NGRS_Solver_Local.postman_environment.json`
2. Set as active environment (top-right dropdown)
3. Variables:
   - `base_url`: http://localhost:8000
   - `admin_api_key`: your-local-key

### Production

1. Import `NGRS_Solver_Production.postman_environment.json`
2. Set as active environment
3. Variables:
   - `base_url`: https://ngrssolver08.comcentricapps.com
   - `admin_api_key`: (set your production key)

## Testing the New Schema

### Quick Test - Day Shift Only

1. Open "Get Optimal Configurations" request
2. Verify body has:
   ```json
   {
     "requirements": [
       {
         "id": "REQ_APO_DAY",
         "shiftTypes": ["D"],
         "headcountPerShift": {
           "D": 4
         }
       }
     ]
   }
   ```
3. Click "Send"
4. Check response includes:
   - `configuration.employeesRequiredPerShift.D`
   - `coverage.requiredPerShift.D`

### Quick Test - Mixed Shifts

1. Open "ICPMP - Mixed Shift Types" request
2. Verify body has:
   ```json
   {
     "requirements": [
       {
         "shiftTypes": ["D", "N"],
         "headcountPerShift": {
           "D": 25,
           "N": 25
         }
       }
     ]
   }
   ```
3. Click "Send"
4. Check response shows both D and N in `employeesRequiredPerShift`

## Collection Structure

```
NGRS Solver API/
├── Health & Info/
│   ├── Health Check
│   ├── API Version
│   └── Input Schema
├── Configuration Optimizer (ICPMP)/      ⭐ UPDATED
│   ├── Get Optimal Configurations       ⭐ NEW SCHEMA
│   └── ICPMP - Mixed Shift Types        ⭐ NEW SCHEMA
├── Synchronous Solve/
│   └── Solve Small Problem
├── Asynchronous Solve/
│   ├── Submit Async Job
│   ├── Get Job Status
│   ├── Get Job Result
│   ├── Cancel Job
│   └── List All Jobs
└── Admin Operations/
    ├── Reset Statistics
    └── Get Statistics
```

## Example Requests

### Single Shift Type (Day Only)
```json
{
  "planningHorizon": {
    "startDate": "2025-12-01",
    "endDate": "2025-12-31"
  },
  "requirements": [
    {
      "id": "REQ_DAY",
      "shiftTypes": ["D"],
      "headcountPerShift": {"D": 5}
    }
  ],
  "constraints": {
    "maxWeeklyNormalHours": 44
  }
}
```

### Multiple Shift Types (Day + Night)
```json
{
  "planningHorizon": {
    "startDate": "2025-12-01",
    "endDate": "2025-12-31"
  },
  "requirements": [
    {
      "id": "REQ_MIXED",
      "shiftTypes": ["D", "N"],
      "headcountPerShift": {
        "D": 10,
        "N": 5
      }
    }
  ],
  "constraints": {
    "maxWeeklyNormalHours": 44
  }
}
```

## Troubleshooting

### Error: "headcountPerShift is required"

**Cause**: Using old schema with `headcountPerDay`

**Solution**: Update request body to use `headcountPerShift` as shown above

### Error: "shifts must be defined for all shiftTypes"

**Cause**: `headcountPerShift` doesn't include all shift types from `shiftTypes`

**Solution**: Ensure every shift type in `shiftTypes` has an entry in `headcountPerShift`

Example:
```json
{
  "shiftTypes": ["D", "N"],
  "headcountPerShift": {
    "D": 10,
    "N": 5
  }
}
```

## Support

For issues or questions:
- Check API documentation: `{{base_url}}/docs`
- Review schema: `{{base_url}}/schema`
- Contact: support@comcentricapps.com

## Version History

- **v0.7.1** (Nov 25, 2025) - Added `headcountPerShift` schema, per-shift output details
- **v0.7.0** (Nov 15, 2025) - ICPMP improvements, top 5 patterns, 100+ employees support
- **v0.6.0** (Oct 2025) - Redis async mode, job management
- **v0.5.0** (Sep 2025) - Initial ICPMP configuration optimizer
