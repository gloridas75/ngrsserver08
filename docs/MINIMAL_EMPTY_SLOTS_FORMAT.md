# Minimal JSON Format for Empty Slots Incremental Solving

**Version:** v0.96  
**Purpose:** Ultra-minimal payload for incremental rostering  
**Target:** <5% of full roster payload size

---

## 🎯 Design Principles

1. **Send only what's needed** - No redundant data
2. **Reference by ID** - Avoid repeating full objects
3. **Compact representation** - Use arrays where possible
4. **Pre-compute on client** - Don't make server recalculate

---

## 📦 Minimal Format Design

### Option 1: Ultra-Minimal (Recommended)

```json
{
  "schemaVersion": "0.96",
  "mode": "incrementalEmptySlots",
  
  "slots": [
    ["2025-12-15", "D", "req_001", "UNASSIGNED"],
    ["2025-12-16", "N", "req_001", "UNASSIGNED"],
    ["2025-12-20", "D", "req_002", "DEPARTED"]
  ],
  
  "lockCtx": {
    "cutoff": "2025-12-10",
    "solveFrom": "2025-12-11",
    "solveTo": "2025-12-31",
    
    "empHrs": {
      "EMP001": [["2025-W50", 32.0], ["2025-W51", 12.0]],
      "EMP002": [["2025-W50", 40.0]]
    },
    
    "empStreak": {
      "EMP001": 3,
      "EMP002": 5
    },
    
    "empLast": {
      "EMP001": "2025-12-10",
      "EMP002": "2025-12-09"
    }
  },
  
  "demandRef": "D_PATROL_ALPHA",
  "employees": ["EMP001", "EMP002", "EMP003"],
  "newEmployees": [
    {
      "employeeId": "EMP999",
      "ouId": "OU-PATROL",
      "teamId": "TEAM-ALPHA",
      "productTypeId": "APO",
      "rankId": "APO",
      "scheme": "A",
      "rotationOffset": 0,
      "gender": "M",
      "qualifications": [
        {"code": "FRISKING-LIC", "validFrom": "2023-01-01", "expiryDate": "2025-12-31"}
      ]
    }
  ]
}
```

**Size Estimate:**
- 50 slots: ~200 bytes
- Lock context: ~500 bytes
- Employee IDs: ~300 bytes
- **Total: ~1 KB** (vs 500 KB for full roster)
- **Reduction: 99.8%** ✅

---

### Option 2: Slightly More Verbose (Better Readability)

```json
{
  "schemaVersion": "0.96",
  "mode": "incrementalEmptySlots",
  
  "emptySlots": [
    {
      "d": "2025-12-15",
      "s": "D",
      "r": "req_001",
      "why": "U"
    },
    {
      "d": "2025-12-16",
      "s": "N",
      "r": "req_001",
      "why": "U"
    },
    {
      "d": "2025-12-20",
      "s": "D",
      "r": "req_002",
      "why": "D"
    }
  ],
  
  "lockedContext": {
    "cutoffDate": "2025-12-10",
    "solveWindow": ["2025-12-11", "2025-12-31"],
    
    "employees": {
      "EMP001": {
        "wh": {"2025-W50": 32.0, "2025-W51": 12.0},
        "str": 3,
        "last": "2025-12-10"
      },
      "EMP002": {
        "wh": {"2025-W50": 40.0},
        "str": 5,
        "last": "2025-12-09"
      }
    }
  },
  
  "demandRef": "D_PATROL_ALPHA",
  "employeeIds": ["EMP001", "EMP002", "EMP003"],
  "newJoiners": [...]
}
```

**Size Estimate:**
- 50 slots: ~800 bytes
- Lock context: ~800 bytes
- Employee refs: ~300 bytes
- **Total: ~2 KB** (vs 500 KB)
- **Reduction: 99.6%** ✅

---

### Option 3: Maximum Compression (For Very Large Scale)

```json
{
  "v": "0.96",
  "m": "ies",
  
  "s": [
    [20251215, "D", 1, 0],
    [20251216, "N", 1, 0],
    [20251220, "D", 2, 1]
  ],
  
  "lc": {
    "c": 20251210,
    "w": [20251211, 20251231],
    
    "e": {
      "1": [[5032, 5112], 3, 20251210],
      "2": [[5040], 5, 20251209]
    }
  },
  
  "dr": "D_PATROL_ALPHA",
  "ei": [1, 2, 3],
  "nj": [...]
}
```

**Encoding:**
- Dates as YYYYMMDD integers or ISO week numbers
- Requirements as numeric IDs
- Reason codes: 0=UNASSIGNED, 1=DEPARTED, 2=LEAVE
- Employee IDs mapped to short integers

**Size Estimate:**
- 50 slots: ~400 bytes
- Lock context: ~400 bytes
- **Total: <1 KB**
- **Reduction: 99.9%** ✅

---

## 🏆 Recommended Format (Balance of Size & Clarity)

```json
{
  "schemaVersion": "0.96",
  "mode": "incrementalEmptySlots",
  
  "emptySlots": [
    {
      "date": "2025-12-15",
      "shift": "D",
      "reqId": "req_001",
      "reason": "UNASSIGNED"
    }
  ],
  
  "locked": {
    "cutoff": "2025-12-10",
    "solve": {
      "from": "2025-12-11",
      "to": "2025-12-31"
    },
    
    "employees": {
      "EMP001": {
        "weekHours": {
          "2025-W50": 32.0,
          "2025-W51": 12.0
        },
        "streak": 3,
        "lastWork": "2025-12-10",
        "offset": 0
      }
    }
  },
  
  "demand": "D_PATROL_ALPHA",
  "pool": ["EMP001", "EMP002", "EMP003"],
  
  "joiners": [
    {
      "employeeId": "EMP999",
      "teamId": "TEAM-ALPHA",
      "productTypeId": "APO",
      "rankId": "APO",
      "scheme": "A",
      "offset": 0,
      "gender": "M",
      "quals": ["FRISKING-LIC", "XRAY-LIC"]
    }
  ]
}
```

---

## 📊 Size Comparison

### Full Roster Approach (Current)
```json
{
  "previousRoster": {
    "assignments": [
      {
        "slotId": "slot_123",
        "date": "2025-12-01",
        "shiftCode": "D",
        "shiftStart": "08:00",
        "shiftEnd": "20:00",
        "employeeId": "ALPHA_001",
        "employeeName": "John Doe",
        "status": "ASSIGNED",
        "requirementId": "req_001",
        "locationId": "ChangiT1",
        "productTypeId": "APO",
        "rankId": "APO",
        "hours": {
          "normal": 12.0,
          "overtime": 0
        },
        "allowances": [...],
        "source": "locked",
        "lockedReason": "before_cutoff"
      },
      // ... 1,549 more assignments
    ],
    "metadata": {...}
  }
}
```

**Size:** ~500 KB for 1,550 assignments

### Empty Slots Approach (Proposed)
```json
{
  "emptySlots": [
    {"date": "2025-12-15", "shift": "D", "reqId": "req_001", "reason": "UNASSIGNED"}
    // ... 49 more slots
  ],
  "locked": {
    "employees": {
      "EMP001": {"weekHours": {"2025-W50": 32}, "streak": 3, "lastWork": "2025-12-10"}
      // ... 49 more employees
    }
  }
}
```

**Size:** ~2-3 KB

**Reduction:** 99.4-99.6% ✅

---

## 🔧 Complete Minimal Schema

### Input Schema (v0.96)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Incremental Empty Slots Request",
  "type": "object",
  "required": ["schemaVersion", "mode", "emptySlots", "locked", "demand", "pool"],
  
  "properties": {
    "schemaVersion": {
      "type": "string",
      "const": "0.96"
    },
    
    "mode": {
      "type": "string",
      "const": "incrementalEmptySlots"
    },
    
    "emptySlots": {
      "type": "array",
      "description": "Slots that need filling",
      "items": {
        "type": "object",
        "required": ["date", "shift", "reqId", "reason"],
        "properties": {
          "date": {"type": "string", "format": "date"},
          "shift": {"type": "string", "pattern": "^[A-Z]+$"},
          "reqId": {"type": "string"},
          "reason": {
            "type": "string",
            "enum": ["UNASSIGNED", "DEPARTED", "LEAVE", "MANUAL"]
          },
          "loc": {"type": "string"},
          "prod": {"type": "string"},
          "rank": {"type": "string"}
        }
      }
    },
    
    "locked": {
      "type": "object",
      "required": ["cutoff", "solve", "employees"],
      "properties": {
        "cutoff": {"type": "string", "format": "date"},
        
        "solve": {
          "type": "object",
          "required": ["from", "to"],
          "properties": {
            "from": {"type": "string", "format": "date"},
            "to": {"type": "string", "format": "date"}
          }
        },
        
        "employees": {
          "type": "object",
          "additionalProperties": {
            "type": "object",
            "properties": {
              "weekHours": {
                "type": "object",
                "additionalProperties": {"type": "number"}
              },
              "monthHours": {"type": "number"},
              "streak": {"type": "integer", "minimum": 0},
              "lastWork": {"type": "string", "format": "date"},
              "offset": {"type": "integer", "minimum": 0}
            }
          }
        }
      }
    },
    
    "demand": {
      "type": "string",
      "description": "Reference to demand item ID"
    },
    
    "pool": {
      "type": "array",
      "description": "Available employee IDs",
      "items": {"type": "string"}
    },
    
    "joiners": {
      "type": "array",
      "description": "New employees joining",
      "items": {
        "type": "object",
        "required": ["employeeId", "teamId", "productTypeId", "rankId", "scheme"],
        "properties": {
          "employeeId": {"type": "string"},
          "teamId": {"type": "string"},
          "productTypeId": {"type": "string"},
          "rankId": {"type": "string"},
          "scheme": {"type": "string", "pattern": "^[A-Z]$"},
          "offset": {"type": "integer"},
          "gender": {"type": "string", "enum": ["M", "F", "Any"]},
          "quals": {
            "type": "array",
            "items": {"type": "string"}
          }
        }
      }
    }
  }
}
```

---

## 💡 Further Optimizations

### 1. Batch Encoding for Repeated Patterns

If many slots share same requirement:
```json
{
  "emptySlots": [
    {
      "reqId": "req_001",
      "dates": [
        ["2025-12-15", "D"],
        ["2025-12-16", "N"],
        ["2025-12-17", "D"]
      ],
      "reason": "UNASSIGNED"
    }
  ]
}
```

**Savings:** 50% for repeated requirements

### 2. Date Range Compression

For consecutive days:
```json
{
  "emptySlots": [
    {
      "dateRange": ["2025-12-15", "2025-12-20"],
      "pattern": ["D", "N", "D", "N", "D", "D"],
      "reqId": "req_001"
    }
  ]
}
```

**Savings:** 60% for consecutive dates

### 3. Delta Encoding for Context

Only send changes from previous locked context:
```json
{
  "locked": {
    "delta": true,
    "employees": {
      "EMP001": {
        "weekHours": {"+2025-W51": 12.0},  // Add to existing
        "streak": "+1"  // Increment by 1
      }
    }
  }
}
```

**Savings:** 70% if most employees unchanged

### 4. Binary Protocol (Advanced)

For extreme scale (1000+ employees, 5000+ slots):
- Use Protocol Buffers or MessagePack
- Binary encoding of dates, IDs
- **Potential size:** <500 bytes for 50 slots
- **Reduction:** 99.95%

---

## 🎯 Practical Example

### Scenario: 50 Empty Slots, 100 Employees

#### Full Roster (Current)
```json
{
  "previousRoster": {
    "assignments": [ /* 3,100 assignments */ ]
  }
}
```
**Size:** ~1.2 MB

#### Minimal Empty Slots (Proposed)
```json
{
  "schemaVersion": "0.96",
  "mode": "incrementalEmptySlots",
  
  "emptySlots": [
    {"date": "2025-12-15", "shift": "D", "reqId": "r1", "reason": "UNASSIGNED"},
    // ... 49 more (1.6 KB)
  ],
  
  "locked": {
    "cutoff": "2025-12-10",
    "solve": {"from": "2025-12-11", "to": "2025-12-31"},
    "employees": {
      "EMP001": {"weekHours": {"2025-W50": 32}, "streak": 3, "lastWork": "2025-12-10"},
      // ... 99 more (4 KB)
    }
  },
  
  "demand": "D_PATROL_ALPHA",
  "pool": ["EMP001", "EMP002", /* ... 98 more (1 KB) */]
}
```
**Size:** ~7 KB

**Reduction:** 99.4% (1.2 MB → 7 KB) ✅

---

## 📋 Field Naming Conventions

### Ultra-Short Keys (Option 1)
```
d     = date
s     = shift
r     = requirementId
why   = reason
wh    = weekHours
str   = streak
lw    = lastWork
off   = offset
```

### Abbreviated Keys (Option 2)
```
date  = date
shift = shift
reqId = requirementId
reas  = reason
wkHrs = weekHours
strk  = streak
last  = lastWork
offs  = offset
```

### Full Keys (Option 3 - Recommended)
```
date           = date
shift          = shift
requirementId  = requirementId
reason         = reason
weekHours      = weekHours
streak         = streak
lastWork       = lastWork
offset         = offset
```

**Recommendation:** Use full keys for clarity, gzip compression handles repetition

---

## 🚀 Implementation Priority

### Phase 1: Basic Minimal Format ✅
```json
{
  "emptySlots": [...],
  "locked": {...},
  "pool": [...]
}
```

### Phase 2: Add Optimizations
- Batch encoding for repeated requirements
- Date range compression

### Phase 3: Advanced (If Needed)
- Delta encoding
- Binary protocol

---

## ✅ Final Recommendation

**Use this format:**

```json
{
  "schemaVersion": "0.96",
  "mode": "incrementalEmptySlots",
  
  "emptySlots": [
    {"date": "2025-12-15", "shift": "D", "reqId": "req_001", "reason": "UNASSIGNED"}
  ],
  
  "locked": {
    "cutoff": "2025-12-10",
    "solve": {"from": "2025-12-11", "to": "2025-12-31"},
    "employees": {
      "EMP_ID": {
        "weekHours": {"2025-W50": 32.0},
        "streak": 3,
        "lastWork": "2025-12-10",
        "offset": 0
      }
    }
  },
  
  "demand": "DEMAND_ID",
  "pool": ["EMP001", "EMP002"],
  "joiners": [...]
}
```

**Benefits:**
- ✅ 99%+ size reduction
- ✅ Clear, readable field names
- ✅ Easy to validate
- ✅ Room for future optimization
- ✅ gzip compresses well

**Achieves:**
- Payload: ~2-5 KB (vs 500 KB)
- Processing: ~10ms (vs 500ms)
- **Total improvement: 99%** 🎯
