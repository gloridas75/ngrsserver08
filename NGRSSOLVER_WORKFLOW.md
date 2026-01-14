# NGRSSOLVER - Complete Workflow Flowchart

## Overall System Workflow

```mermaid
flowchart TD
    Start([User Request]) --> Interface{Entry Point?}

    Interface -->|REST API| API[FastAPI Server<br/>api_server.py]
    Interface -->|Command Line| CLI[CLI Tool<br/>run_solver.py]
    Interface -->|Async Job| REDIS[Redis Job Queue<br/>redis_worker.py]

    API --> Solver[Unified Solver Core<br/>solver.py]
    CLI --> Solver
    REDIS --> Solver

    Solver --> Validate[Phase 1: Input Validation<br/>input_validator.py]

    Validate --> ValidCheck{Valid Input?}
    ValidCheck -->|No| Error1[Return Error:<br/>Schema Violation]
    ValidCheck -->|Yes| Preprocess

    Preprocess[Phase 2: Preprocessing Decision] --> HasPattern{Employees Have<br/>Work Patterns?}

    HasPattern -->|Yes| OffsetStagger[Offset Staggering<br/>offset_manager.py<br/>Adjust rotation offsets]
    HasPattern -->|No| ICPMP[ICPMP v3.0 Preprocessing<br/>icpmp_integration.py]

    ICPMP --> ICPMP1[Calculate Optimal<br/>Employee Count]
    ICPMP1 --> ICPMP2[Filter by Scheme &<br/>Qualifications]
    ICPMP2 --> ICPMP3[Select Balanced Subset<br/>14-20 from 100+]
    ICPMP3 --> ICPMP4[Assign Rotation<br/>Offsets 0-5]
    ICPMP4 --> DataLoad

    OffsetStagger --> DataLoad[Phase 3: Data Loading<br/>data_loader.py]

    DataLoad --> DataLoad1[Load & Normalize<br/>Input JSON]
    DataLoad1 --> DataLoad2[Build OU Mappings]
    DataLoad2 --> DataLoad3[Extract Rostering Basis]
    DataLoad3 --> SlotGen

    SlotGen[Phase 4: Slot Generation<br/>slot_builder.py] --> SlotGen1[Convert Demand Items<br/>to Shift Slots]
    SlotGen1 --> SlotGen2[Apply Rotation Patterns<br/>D-D-N-N-O-O-O]
    SlotGen2 --> SlotGen3[Generate Daily Slots<br/>for Planning Horizon]
    SlotGen3 --> SlotGen4[Apply Shift Times &<br/>Qualifications]
    SlotGen4 --> SlotOutput[Output: 1000s of<br/>Slot Objects]

    SlotOutput --> ModelBuild[Phase 5: CP-SAT Model Building<br/>solver_engine.py]

    ModelBuild --> CreateVars[Create Decision Variables<br/>x for slot,emp in 0,1]
    CreateVars --> FilterPairs[Filter Employee-Slot Pairs]

    FilterPairs --> Filter1[Product Type Match]
    Filter1 --> Filter2[Rank Match OR Logic]
    Filter2 --> Filter3[Gender Requirements]
    Filter3 --> Filter4[Scheme Matching]
    Filter4 --> Filter5[Blacklist Dates]
    Filter5 --> UnassignedVars[Create Unassigned<br/>Slot Variables]

    UnassignedVars --> ConstraintApp[Phase 6: Constraint Application<br/>solver_engine.py]

    ConstraintApp --> HardConst[Apply Hard Constraints<br/>C1-C19]

    HardConst --> C1[C1: Daily Hours Cap<br/>14h/13h/9h by scheme]
    C1 --> C2[C2: Weekly Normal Hours<br/>44-52h limits]
    C2 --> C3[C3: Consecutive Days<br/>Maximum work days]
    C3 --> C4[C4: Rest Period<br/>Min hours between shifts]
    C4 --> C5to19[C5-C19: Off-days, Licensing<br/>Gender, Teams, OT Caps...]

    C5to19 --> SoftConst[Apply Soft Constraints<br/>S1-S17]

    SoftConst --> S1[S1: Pattern Adherence<br/>Minimize deviations]
    S1 --> S2[S2: Shift Preferences<br/>Employee preferences]
    S2 --> S3[S3: Consistent Start Times<br/>Shift continuity]
    S3 --> S4to17[S4-S17: Team Cohesion<br/>Travel, Fairness...]

    S4to17 --> Objective[Build Objective Function<br/>Minimize Penalty Score]

    Objective --> CPSATSolve[Phase 7: OR-Tools CP-SAT Solving<br/>Google OR-Tools Engine]

    CPSATSolve --> ConfigSolver[Configure Solver Parameters]
    ConfigSolver --> TimeLimit[Time Limit: 5-60s<br/>Adaptive]
    TimeLimit --> Workers[Parallel Workers: 1-16<br/>Based on complexity]
    Workers --> Execute[Execute Constraint<br/>Programming]

    Execute --> SolveStatus{Solution<br/>Status?}

    SolveStatus -->|OPTIMAL| Extract[Phase 8: Solution Extraction]
    SolveStatus -->|FEASIBLE| Extract
    SolveStatus -->|INFEASIBLE| Infeasible[Mark as Infeasible<br/>Record unmet demand]

    Infeasible --> Extract

    Extract --> ExtractAssign[Extract Assignments<br/>from Solution]
    ExtractAssign --> CalcViolations[Calculate Hard/Soft<br/>Violations]
    CalcViolations --> ComputeScores[Compute Scores]

    ComputeScores --> OutputBuild[Phase 9: Output Building<br/>output_builder.py]

    OutputBuild --> FormatJSON[Format Results to<br/>JSON Schema v0.95+]
    FormatJSON --> CalcHours[Calculate Employee Hours<br/>Normal, OT, Monthly]
    CalcHours --> BuildRoster[Build Employee Roster<br/>Daily status per employee]
    BuildRoster --> GenMeta[Generate Metadata<br/>Timing, hash, warnings]
    GenMeta --> ScoreBreakdown[Create Score Breakdown<br/>Violation analysis]

    ScoreBreakdown --> OutputJSON[Output JSON File]

    OutputJSON --> OutputStructure{Output Contains:}

    OutputStructure --> Assignments[assignments: Work shifts]
    OutputStructure --> EmployeeRoster[employeeRoster: Daily schedules]
    OutputStructure --> UnmetDemand[unmetDemand: Unfilled slots]
    OutputStructure --> ScoreDetails[scoreBreakdown: Violations]
    OutputStructure --> SolverMeta[solverRun: Execution metadata]

    Assignments --> End([Return to User])
    EmployeeRoster --> End
    UnmetDemand --> End
    ScoreDetails --> End
    SolverMeta --> End
    Error1 --> End

    style Start fill:#e1f5e1
    style End fill:#ffe1e1
    style Solver fill:#e1e5ff
    style ICPMP fill:#fff4e1
    style CPSATSolve fill:#ffe1f5
    style OutputJSON fill:#e1f5e1
    style Error1 fill:#ffcccc
```

## Detailed Phase Breakdown

### Phase 1: Input Validation
```mermaid
flowchart LR
    A[Input JSON] --> B{Schema v0.95<br/>Valid?}
    B -->|No| C[Error: Invalid Schema]
    B -->|Yes| D{Employee Count<br/>Valid?}
    D -->|No| E[Error: Invalid Count]
    D -->|Yes| F{Demand Items<br/>Valid?}
    F -->|No| G[Error: Invalid Demand]
    F -->|Yes| H{Date Range<br/>Valid?}
    H -->|No| I[Error: Invalid Dates]
    H -->|Yes| J[Validation Passed]

    style C fill:#ffcccc
    style E fill:#ffcccc
    style G fill:#ffcccc
    style I fill:#ffcccc
    style J fill:#ccffcc
```

### Phase 2: ICPMP Preprocessing Flow
```mermaid
flowchart TD
    A[100+ Employees<br/>No Patterns] --> B[Analyze Demand<br/>Requirements]
    B --> C[Calculate Min<br/>Employee Count]
    C --> D[Try-Minimal-First<br/>Algorithm]

    D --> E[Filter Candidates]
    E --> F[By Scheme A/B/P]
    F --> G[By Qualifications]
    G --> H[By Availability]

    H --> I[Rank Candidates]
    I --> J[Prefer Less-Loaded]
    J --> K[Ensure Scheme Diversity]
    K --> L[Apply Seniority Tiebreak]

    L --> M[Select Top 14-20<br/>Employees]
    M --> N[Assign Rotation<br/>Offsets 0-5]
    N --> O[Stagger Coverage<br/>Across Week]

    O --> P[Optimized Employee<br/>Subset Ready]

    style A fill:#ffe1e1
    style P fill:#e1f5e1
```

### Phase 3: Slot Generation Process
```mermaid
flowchart TD
    A[Demand Items] --> B{For Each<br/>Requirement}

    B --> C[Get Work Pattern<br/>e.g., D-D-N-N-O-O-O]
    C --> D[Get Planning Horizon<br/>Start/End Dates]
    D --> E[Get Shift Times<br/>Start/End/Duration]

    E --> F{For Each Day<br/>in Horizon}

    F --> G[Calculate Pattern Day<br/>offset % pattern_length]
    G --> H{Pattern Code?}

    H -->|D Day Shift| I[Create Day Slot<br/>07:00-15:00]
    H -->|N Night Shift| J[Create Night Slot<br/>23:00-07:00]
    H -->|O Off Day| K[Skip - No Slot]

    I --> L[Apply Qualifications]
    J --> L
    K --> F

    L --> M[Apply Rank Requirements]
    M --> N[Apply Scheme]
    N --> O[Apply Gender Rules]
    O --> P[Add to Slot List]

    P --> F
    F -->|All Days Done| Q[1000s of Slots<br/>Generated]

    style A fill:#e1e5ff
    style Q fill:#e1f5e1
```

### Phase 4: CP-SAT Model Building
```mermaid
flowchart TD
    A[Slots + Employees] --> B[Create Binary Variables<br/>x_slot,emp]

    B --> C{For Each Slot}
    C --> D{For Each Employee}

    D --> E{Can Assign?}

    E -->|Check 1| F[Product Type Match?]
    F -->|No| G[Skip Pair]
    F -->|Yes| H[Rank Match?<br/>OR logic]
    H -->|No| G
    H -->|Yes| I[Gender Match?]
    I -->|No| G
    I -->|Yes| J[Scheme Match?]
    J -->|No| G
    J -->|Yes| K[Not Blacklisted?]
    K -->|No| G
    K -->|Yes| L[Create Variable<br/>x_slot,emp]

    L --> D
    G --> D

    D -->|All Employees| C
    C -->|All Slots| M[Create Unassigned<br/>Variables]

    M --> N[Add Constraint:<br/>Each slot assigned once<br/>OR unassigned]

    N --> O[Model Built<br/>Ready for Constraints]

    style A fill:#e1e5ff
    style O fill:#e1f5e1
```

### Phase 5: Constraint Evaluation
```mermaid
flowchart TD
    A[CP-SAT Model] --> B{Apply Hard<br/>Constraints}

    B --> C1[C1: Daily Hours <= Cap]
    B --> C2[C2: Weekly Hours <= Limit]
    B --> C3[C3: Consecutive Days <= Max]
    B --> C4[C4: Rest Hours >= Min]
    B --> C5[C5-C19: Other Hard Rules]

    C1 --> D{All Hard<br/>Satisfied?}
    C2 --> D
    C3 --> D
    C4 --> D
    C5 --> D

    D -->|No| E[Solution = INFEASIBLE]
    D -->|Yes| F{Apply Soft<br/>Constraints}

    F --> S1[S1: Pattern Adherence<br/>Penalty = deviations * weight]
    F --> S2[S2: Shift Preferences<br/>Penalty = mismatches * weight]
    F --> S3[S3: Consistent Times<br/>Penalty = variations * weight]
    F --> S4[S4-S17: Other Preferences]

    S1 --> G[Sum All Penalties]
    S2 --> G
    S3 --> G
    S4 --> G

    G --> H[Objective = Minimize<br/>Total Penalty Score]

    H --> I[Ready for Solving]
    E --> I

    style D fill:#fff4e1
    style H fill:#e1f5e1
    style E fill:#ffcccc
```

### Phase 6: OR-Tools Solving Process
```mermaid
flowchart TD
    A[CP-SAT Model<br/>with Constraints] --> B[Configure Solver]

    B --> C[Set Time Limit<br/>5-60 seconds adaptive]
    C --> D[Set Parallel Workers<br/>1-16 based on size]
    D --> E[Enable Logging]

    E --> F[Start CP-SAT Solver]

    F --> G{Solving...}

    G --> H{Found Solution<br/>within Time?}

    H -->|Yes, Best| I[Status: OPTIMAL<br/>Score = 0 violations]
    H -->|Yes, Good| J[Status: FEASIBLE<br/>Score > 0]
    H -->|No| K[Status: INFEASIBLE<br/>No valid solution]

    I --> L[Extract Solution]
    J --> L
    K --> M[Extract Partial<br/>Solution]

    L --> N[Return Assignments]
    M --> O[Return Unmet Demand]

    N --> P[Solution Ready]
    O --> P

    style I fill:#ccffcc
    style J fill:#ffffcc
    style K fill:#ffcccc
    style P fill:#e1f5e1
```

### Phase 7: Output Building
```mermaid
flowchart TD
    A[Solver Solution] --> B[Extract Assignments]

    B --> C{For Each<br/>Assignment}

    C --> D[Get Employee ID]
    D --> E[Get Slot Details]
    E --> F[Calculate Hours<br/>Normal + OT]
    F --> G[Create Assignment Object]

    G --> C
    C -->|All Done| H[Build Employee Roster]

    H --> I{For Each<br/>Employee}

    I --> J[Get Work Pattern]
    J --> K[Get Rotation Offset]
    K --> L{For Each Day}

    L --> M{Day Status?}
    M -->|Assigned| N[Status: ASSIGNED<br/>Add shift details]
    M -->|Off Day| O[Status: OFF_DAY]
    M -->|Not Assigned| P[Status: UNASSIGNED]
    M -->|Not Used| Q[Status: NOT_USED]

    N --> L
    O --> L
    P --> L
    Q --> L

    L -->|All Days| I
    I -->|All Employees| R[Calculate Scores]

    R --> S[Hard Violation Count]
    S --> T[Soft Violation Count]
    T --> U[Overall Score]

    U --> V[Generate Metadata]
    V --> W[Request ID<br/>Timestamps<br/>Input Hash]

    W --> X[Build Final JSON]

    X --> Y{JSON Contains}

    Y --> Z1[assignments array]
    Y --> Z2[employeeRoster array]
    Y --> Z3[unmetDemand array]
    Y --> Z4[scoreBreakdown object]
    Y --> Z5[solverRun metadata]
    Y --> Z6[meta object]

    Z1 --> AA[Output JSON v0.95+<br/>Complete]
    Z2 --> AA
    Z3 --> AA
    Z4 --> AA
    Z5 --> AA
    Z6 --> AA

    style A fill:#e1e5ff
    style AA fill:#e1f5e1
```

## Rostering Mode Decision Tree

```mermaid
flowchart TD
    A[Demand Items] --> B{Rostering<br/>Basis?}

    B -->|demandBased| C[Demand-Based Mode]
    B -->|outcomeBased| D[Outcome-Based Mode]

    C --> E[Must Fill ALL<br/>Specified Slots]
    E --> F[Solver finds employees<br/>for each slot]
    F --> G{All Slots<br/>Filled?}
    G -->|Yes| H[OPTIMAL/FEASIBLE]
    G -->|No| I[INFEASIBLE<br/>Record unmet demand]

    D --> J[Determine Min<br/>Employee Count]
    J --> K[ICPMP Preprocessing<br/>Select optimal subset]
    K --> L[Generate roster with<br/>selected employees]
    L --> M{Meets Min<br/>Threshold?}
    M -->|Yes| N[OPTIMAL/FEASIBLE]
    M -->|No| O[INFEASIBLE<br/>Insufficient employees]

    H --> P[Return Solution]
    I --> P
    N --> P
    O --> P

    style C fill:#e1f5ff
    style D fill:#ffe1f5
    style H fill:#ccffcc
    style N fill:#ccffcc
    style I fill:#ffcccc
    style O fill:#ffcccc
```

## Time Calculation Flow

```mermaid
flowchart TD
    A[Assignment] --> B[Get Shift Times<br/>Start/End]

    B --> C[Calculate Gross Hours<br/>End - Start]

    C --> D{Is Public<br/>Holiday?}
    D -->|Yes| E[All Hours = Paid Leave]
    D -->|No| F{Scheme Type?}

    F -->|Scheme A/B| G[Check Daily Cap<br/>Normal vs OT]
    F -->|Scheme P| H[All Hours = Normal<br/>Max 9h/day]

    G --> I{Hours > 8?}
    I -->|No| J[All Hours = Normal]
    I -->|Yes| K[First 8h = Normal<br/>Rest = OT]

    J --> L[Add to Weekly Total]
    K --> L
    H --> L
    E --> M[Add to Paid Leave]

    L --> N{Weekly Total<br/>> 44h?}
    N -->|Yes| O[Hours 45-52 = OT<br/>Reclassify from Normal]
    N -->|No| P[Keep as Normal]

    O --> Q[Monthly Totals]
    P --> Q
    M --> Q

    Q --> R{Monthly OT<br/>> 72h?}
    R -->|Yes| S[VIOLATION<br/>C17: OT Cap]
    R -->|No| T[Compliant]

    S --> U[Record Violation]
    T --> V[Hours Valid]

    U --> W[Final Hours<br/>Normal, OT, Leave]
    V --> W

    style A fill:#e1e5ff
    style W fill:#e1f5e1
    style S fill:#ffcccc
    style T fill:#ccffcc
```

## System Integration Overview

```mermaid
flowchart LR
    A[External Systems] --> B{API Gateway}

    B --> C[REST API<br/>FastAPI]
    B --> D[Redis Queue<br/>Async Jobs]

    C --> E[Solver Core]
    D --> F[Worker Process]
    F --> E

    E --> G[OR-Tools<br/>CP-SAT Engine]

    G --> H[Solution]

    H --> I[Output Builder]
    I --> J[JSON Response]

    J --> K[File System<br/>output/]
    J --> L[HTTP Response]
    J --> M[Redis Result Store]

    K --> N[Web Dashboard<br/>Viewer]
    L --> O[API Client]
    M --> P[Job Status Query]

    style A fill:#e1e5ff
    style E fill:#ffe1f5
    style G fill:#fff4e1
    style J fill:#e1f5e1
```

---

## How to View This Flowchart

### In VS Code:
1. Install "Markdown Preview Mermaid Support" extension
2. Open this file and press `Cmd+Shift+V` (Mac) or `Ctrl+Shift+V` (Windows)
3. Flowcharts will render interactively

### In GitHub:
- GitHub automatically renders Mermaid diagrams in markdown files

### Online:
- Copy the mermaid code blocks to https://mermaid.live for interactive editing

---

**NGRSSOLVER v0.96.0**
**Documentation Generated**: 2026-01-13
