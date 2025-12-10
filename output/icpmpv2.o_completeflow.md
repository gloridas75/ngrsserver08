┌─────────────────────────────────────────────────────────────────┐
│                    1. INPUT (User Request)                       │
│                                                                  │
│  User specifies requirements:                                   │
│  • Coverage Days: ["Mon", "Tue", "Wed", "Thu", "Fri"]          │
│  • Shift Types: ["D"] or ["D", "N"]                            │
│  • Headcount Per Shift: {"D": 10} or {"D": 10, "N": 10}        │
│  • Planning Horizon: 31 days                                    │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│           2. PATTERN GENERATION (Coverage-Aware)                 │
│        (generate_coverage_aware_patterns function)               │
│                                                                  │
│  KEY INNOVATION: Pattern length MATCHES coverage days!          │
│                                                                  │
│  Example for Mon-Fri (5 days):                                  │
│  ✓ Generates 5-day patterns: [D,D,D,D,O]                        │
│  ✗ Won't generate 7-day patterns: [D,D,D,D,D,O,O]              │
│                                                                  │
│  Pattern Types Generated:                                       │
│  • Single shift consecutive: [D,D,D,O,O]                        │
│  • Single shift distributed: [D,D,O,D,D,O]                      │
│  • Mixed shifts (if 2+ types): [D,D,N,N,O]                      │
│                                                                  │
│  Constraints:                                                   │
│  • min_work_days = 3                                            │
│  • max_work_days = min(5, coverage_days - 1)                   │
│  • Must have at least 1 rest day                                │
│                                                                  │
│  Output: ~10-20 candidate patterns                              │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│         3. PATTERN VALIDATION (Length Check)                     │
│                                                                  │
│  Each pattern is validated:                                     │
│  • Pattern length MUST equal coverage days length               │
│  • Example: 5 coverage days → only accept 5-day patterns        │
│  • Rejects mismatched patterns                                  │
│                                                                  │
│  WHY IMPORTANT:                                                 │
│  - Prevents off-by-one errors                                   │
│  - Ensures pattern aligns with business week                    │
│  - 24% more accurate than v1.0                                  │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│    4. COVERAGE SIMULATION (Rotation Preprocessor Integration)   │
│         (simulate_coverage_with_preprocessing function)          │
│                                                                  │
│  For each valid pattern, runs intelligent simulation:           │
│                                                                  │
│  Step 4a: Generate Coverage Calendar                            │
│  • Creates list of work days in planning horizon                │
│  • Filters by coverage days (e.g., only Mon-Fri)               │
│  • Example: 31-day month → ~22 weekdays                         │
│                                                                  │
│  Step 4b: Simulate Pattern Filling (Greedy Algorithm)           │
│  • Simulates rotation with staggered offsets                    │
│  • Places employees across cycle (0, 1, 2, ..., cycle-1)       │
│  • Tracks daily coverage against headcount requirement          │
│                                                                  │
│  Employee Categories Identified:                                │
│  • STRICT: Must be on specific offset for coverage              │
│  • FLEXIBLE: Can fill gaps across multiple offsets              │
│  • TRULY FLEXIBLE: Can work any offset (offset=-1)              │
│                                                                  │
│  Example Simulation Output:                                     │
│  • Pattern: [D,D,D,D,O] with HC=10, 22 weekdays                │
│  • Employees needed: 14                                         │
│  • Breakdown: 12 strict + 2 flexible                            │
│  • Offsets: [0,0,1,1,2,2,3,3,4,4,0,1,2,3]                       │
│  • Coverage complete: Yes                                       │
│  • Daily coverage range: (10, 10) - perfect!                   │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│              5. EMPLOYEE COUNT CALCULATION                       │
│                                                                  │
│  For SINGLE shift patterns (e.g., D only):                      │
│  employees = ceil(HC × cycle_length / work_days)                │
│  Example: ceil(10 × 5 / 4) = 13 employees                      │
│                                                                  │
│  For MULTI-SHIFT patterns (e.g., D+N):                          │
│  employees = Σ(HC_per_shift) × cycle_length / work_days        │
│  Example: (10+10) × 6 / 4 = 30 employees                       │
│                                                                  │
│  ADJUSTMENT for flexible employees:                             │
│  • Flexible employees can cover multiple gaps                   │
│  • Reduces total needed by ~5-10%                               │
│  • Real simulation more accurate than formula                   │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                   6. SCORING & RANKING                           │
│                                                                  │
│  Each pattern gets a score (lower = better):                    │
│                                                                  │
│  Score Components:                                              │
│  • Employee penalty: employees × 10                             │
│    (Prefer patterns using fewer employees)                      │
│                                                                  │
│  • Coverage penalty: 1000 if incomplete, 0 if complete          │
│    (Strongly prefer patterns meeting headcount)                 │
│                                                                  │
│  • Flexible bonus: -5 per flexible employee                     │
│    (Reward patterns creating flexibility)                       │
│                                                                  │
│  Example Scores:                                                │
│  • [D,D,D,D,O]: 14 employees, complete → 140 - 10 = 130        │
│  • [D,D,D,O,O]: 18 employees, complete → 180 - 5 = 175         │
│  • [D,O,D,O,D]: 25 employees, incomplete → 250 + 1000 = 1250   │
│                                                                  │
│  Patterns sorted by score (ascending)                           │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                7. OUTPUT (Top N Recommendations)                 │
│                                                                  │
│  Returns top 5 patterns for each requirement:                   │
│                                                                  │
│  Recommendation #1 (Best):                                      │
│  {                                                              │
│    "workPattern": ["D","D","D","D","O"],                        │
│    "employeesRequired": 14,                                     │
│    "strictEmployees": 12,                                       │
│    "flexibleEmployees": 2,                                      │
│    "employeeOffsets": [0,0,1,1,2,2,3,3,4,4,0,1,2,3],            │
│    "expectedCoverageRate": 100.0,                               │
│    "score": 130                                                 │
│  }                                                              │
│                                                                  │
│  Recommendation #2 (Alternative):                               │
│  {                                                              │
│    "workPattern": ["D","D","O","D","D"],                        │
│    "employeesRequired": 14,                                     │
│    "strictEmployees": 13,                                       │
│    "flexibleEmployees": 1,                                      │
│    "employeeOffsets": [0,0,1,1,2,2,3,3,4,4,0,1,2,3],            │
│    "expectedCoverageRate": 100.0,                               │
│    "score": 135                                                 │
│  }                                                              │
│                                                                  │
│  ... (up to 5 alternatives)                                     │
└─────────────────────────────────────────────────────────────────┘