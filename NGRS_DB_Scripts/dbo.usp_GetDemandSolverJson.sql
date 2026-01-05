USE [NGRS]
GO
/****** Object:  StoredProcedure [dbo].[usp_GetDemandSolverJson]    Script Date: 1/3/2026 7:28:45 PM ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO


/*
===============================================================================
 Procedure Name : dbo.usp_GetDemandSolverJson
 Database       : NGRS

 Purpose:
   Generates JSON payload for solver API based on DemandItem, including:
   - Demand metadata
   - Shift definitions & coverage config (incl. PH + eve-of-PH flags)
   - Requirements
   - Eligible employee pool

 Employee Filtering Pipeline (Refactored):
   A) #EmpBaseEmployees      : Active employees only
   B) #EmpWhitelistedEmployees: From WhitelistTeam + WhitelistEmployee
   C) #EmpCandidateEmployees : OrgUnit pool (plus whitelist union in INCLUSIVE mode)
   D) #EmpFinalEmployees     : Requirement-matched candidates (productType, rank, scheme, gender, qualifications)
   E) Exclusions             : Blacklist (date aware) + Rostered (mode dependent)
   F) JSON                   : Build employee JSON from final set (qualifications filtered to demand requirements)

 Local Whitelist Mode (NOT a parameter):
   @WhitelistMode = 'INCLUSIVE' | 'STRICT'
   - INCLUSIVE (default):
       Whitelist employees ALWAYS included +
       Other OrgUnit employees included if requirement filters match
   - STRICT:
       If whitelist exists -> ONLY whitelisted employees are considered
       If no whitelist -> behave like INCLUSIVE (OrgUnit + requirements)

 Version History:
   v2.2 - 2025-12-16 : Staged employee filtering pipeline
   v2.3 - 2025-12-16 : Added local WhitelistMode (STRICT/INCLUSIVE) + fixed logic
   v2.4 - 2025-12-16 : Added WhitelistOrgUnit support + teamOffsets JSON for rotation
   v2.5 - 2025-12-18 : Multi-rank support via DemandRequirementRank junction table
   v2.6 - 2025-12-18 : Fixed whitelist filtering - requirement filters (productType, rank,
                       scheme, gender) now apply to ALL candidates including whitelisted.
                       Whitelist defines the candidate POOL, not a filter bypass.
   v2.7 - 2025-12-19 : Fixed mixed shifts handling:
                       - shiftDetails: Use fn_GetDemandShiftDetailsJson for proper shift codes
                       - workPattern: Use fn_GetShiftCodeByNumber to map pattern numbers (1,2)
                         to individual shift codes (D,N) instead of using entire ShiftCode string
   v2.8 - 2025-12-22 : Multi-scheme support via DemandRequirementScheme junction table
                       - Requirements JSON: "schemes" array replaces single "scheme" field
                       - Output format: ["Scheme A", "Scheme B"] or ["Any"] for all schemes
                       - Employee filtering: Uses #EmpRequirementSchemes from junction table
   v2.9 - 2025-12-30 : Added enableOtAwareIcpmp toggle and offboarding unavailability
                       - enableOtAwareIcpmp: false for outcomeBased, true for demandBased
                       - F.4: Added offboarding dates to unavailability (DateOfLeaving onwards)
   v3.0 - 2025-12-31 : Qualification-based employee filtering and output
                       - Added #DemandRequiredQualifications temp table from DemandConstraint
                       - Step D: Employees must have at least 1 matching qualification (if demand has constraints)
                       - Employee JSON: qualifications array now only includes demand-relevant qualifications
                       - No longer outputs all employee qualifications blindly
   v3.1 - 2026-01-04 : Fixed qualification code format mismatch and strict demandBased filtering
                       - Changed from ConstraintValue to ConstraintName for qualification codes
                       - demandBased (INCLUSIVE): ALL employees must match requirement filters (productType, rank, scheme, gender, qualifications)
                       - outcomeBased (STRICT): Whitelisted employees bypass requirement filters (explicit override)
                       - Ensures only qualified employees are rostered in demandBased mode

 Last Updated:
   2026-01-04 (UTC+08:00)
===============================================================================
*/
ALTER PROCEDURE [dbo].[usp_GetDemandSolverJson]
    @DemandItemId INT,
    @StartDate DATE = NULL,
    @RosterFlexibility NVARCHAR(50) = 'newOfficers'
AS
BEGIN
    SET NOCOUNT ON;

    BEGIN TRY

        --------------------------------------------------------------------
        -- 0) Resolve demand + context
        --------------------------------------------------------------------
        DECLARE @DemandCode NVARCHAR(50);
        DECLARE @LocationId INT;
        DECLARE @LocationCode NVARCHAR(50);
        DECLARE @DemandStartDate DATE;
        DECLARE @WorkItemId INT;
        DECLARE @OrgUnitCode NVARCHAR(50);
        DECLARE @OrgUnitId BIGINT;
        DECLARE @PlannerGroupId INT;
        DECLARE @CoverageDaysOfWeek NVARCHAR(100);

        -- Local feature toggle (NOT a parameter)
        -- Dynamically set based on IsOutcomeBased:
        --   outcomeBased (IsOutcomeBased=1) -> STRICT (only whitelisted employees)
        --   demandBased (IsOutcomeBased=0) -> INCLUSIVE (OrgUnit + whitelisted)
        DECLARE @WhitelistMode NVARCHAR(20);
        -- Allowed: 'INCLUSIVE' | 'STRICT'

        SELECT
            @DemandCode = di.DemandItemCode,
            @LocationId = di.LocationId,
            @DemandStartDate = di.StartDate,
            @WorkItemId = di.WorkItemId
        FROM DemandItem di
        WHERE di.Id = @DemandItemId AND di.IsActive = 1;

        IF @StartDate IS NULL
            SET @StartDate = @DemandStartDate;

        -- Calculate EndDate as end of month from StartDate (used for unavailability date range)
        DECLARE @EndDate DATE = EOMONTH(@StartDate);

        IF @DemandCode IS NULL
        BEGIN
            RAISERROR('Demand item with ID %d not found or is inactive', 16, 1, @DemandItemId);
            RETURN;
        END

        SELECT @LocationCode = LocationCode
        FROM Location
        WHERE LocationId = @LocationId;

        -- Set WhitelistMode based on IsOutcomeBased from DemandCoverageConfiguration:
        -- If the coverage is outcomeBased (IsOutcomeBased=1), use STRICT mode
        IF EXISTS (
            SELECT 1 FROM DemandCoverageConfiguration
            WHERE DemandItemId = @DemandItemId
              AND IsActive = 1
              AND IsOutcomeBased = 1
        )
            SET @WhitelistMode = 'STRICT';
        ELSE
            SET @WhitelistMode = 'INCLUSIVE';

        SELECT
            @OrgUnitCode = ou.SAP_OrgCode,
            @OrgUnitId = ou.OrgUnitId,
            @PlannerGroupId = wi.PlannerGroupId
        FROM WorkItem wi
        INNER JOIN OrgUnit ou ON wi.OrgUnitId = ou.OrgUnitID
        WHERE wi.Id = @WorkItemId;

        SELECT TOP 1 @CoverageDaysOfWeek = c.DaysOfWeek
        FROM DemandCoverageConfiguration dcc
        INNER JOIN Coverage c ON dcc.CoverageTemplateId = c.Id
        WHERE dcc.DemandItemId = @DemandItemId AND dcc.IsActive = 1;

        -- Get rosteringBasis and minStaffThresholdPercentage from DemandCoverageConfiguration for demandItem level
        DECLARE @RosteringBasis NVARCHAR(20) = 'demandBased';
        DECLARE @MinStaffThresholdPercentage INT = 100;
        SELECT TOP 1
            @RosteringBasis = CASE WHEN dcc.IsOutcomeBased = 1 THEN 'outcomeBased' ELSE 'demandBased' END,
            @MinStaffThresholdPercentage = ISNULL(dcc.MinStaffThreshold, 100)
        FROM DemandCoverageConfiguration dcc
        WHERE dcc.DemandItemId = @DemandItemId AND dcc.IsActive = 1;

        --------------------------------------------------------------------
        -- 1) Shift details JSON
        --    Uses fn_GetDemandShiftDetailsJson which handles both:
        --    - Specific shifts (DemandCoverageId linked)
        --    - Mixed shifts (DemandCoverageId IS NULL, ShiftCode like 'D,N')
        --------------------------------------------------------------------
        DECLARE @ShiftDetailsJson NVARCHAR(MAX);

        SET @ShiftDetailsJson = dbo.fn_GetDemandShiftDetailsJson(@DemandItemId);

        DECLARE @IncludePublicHolidays BIT = 0;
        SELECT @IncludePublicHolidays = ISNULL(MAX(CAST(IncludePublicHolidays AS INT)), 0)
        FROM DemandCoverageShift dcs
        WHERE dcs.CoverageConfigurationId IN (
            SELECT Id FROM DemandCoverageConfiguration
            WHERE DemandItemId = @DemandItemId AND IsActive = 1
        );

        DECLARE @IncludeEveOfPublicHolidays BIT = 0;
        SELECT @IncludeEveOfPublicHolidays = ISNULL(MAX(CAST(IncludeEveOfPublicHolidays AS INT)), 0)
        FROM DemandCoverageShift dcs
        WHERE dcs.CoverageConfigurationId IN (
            SELECT Id FROM DemandCoverageConfiguration
            WHERE DemandItemId = @DemandItemId AND IsActive = 1
        );

        --------------------------------------------------------------------
        -- 2) Coverage days JSON
        --------------------------------------------------------------------
        DECLARE @CoverageDaysJson NVARCHAR(MAX);

        IF @CoverageDaysOfWeek IS NOT NULL AND LEN(@CoverageDaysOfWeek) > 0
        BEGIN
            SELECT @CoverageDaysJson = (
                SELECT
                    CASE LTRIM(RTRIM(value))
                        WHEN '1' THEN 'Mon'
                        WHEN '2' THEN 'Tue'
                        WHEN '3' THEN 'Wed'
                        WHEN '4' THEN 'Thu'
                        WHEN '5' THEN 'Fri'
                        WHEN '6' THEN 'Sat'
                        WHEN '7' THEN 'Sun'
                        WHEN '0' THEN 'Sun'
                        ELSE LTRIM(RTRIM(value))
                    END AS [value]
                FROM STRING_SPLIT(@CoverageDaysOfWeek, ',')
                FOR JSON PATH
            );

            SET @CoverageDaysJson = REPLACE(REPLACE(@CoverageDaysJson, '{"value":"', '"'), '"}', '"');
        END
        ELSE
            SET @CoverageDaysJson = '["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]';

        --------------------------------------------------------------------
        -- 3) Whitelist/Blacklist JSON blocks (for solver payload)
        --------------------------------------------------------------------
        DECLARE @WhitelistTeamIdsJson NVARCHAR(MAX);
        SELECT @WhitelistTeamIdsJson = (
            SELECT t.TeamCode AS [value]
            FROM WhitelistTeam wt
            INNER JOIN Team t ON wt.TeamId = t.TeamID
            WHERE wt.DemandItemId = @DemandItemId AND wt.IsActive = 1
            FOR JSON PATH
        );

        IF @WhitelistTeamIdsJson IS NOT NULL
            SET @WhitelistTeamIdsJson = REPLACE(REPLACE(@WhitelistTeamIdsJson, '{"value":"', '"'), '"}', '"');
        ELSE
            SET @WhitelistTeamIdsJson = '[]';

        DECLARE @WhitelistEmployeeIdsJson NVARCHAR(MAX);
        SELECT @WhitelistEmployeeIdsJson = (
            SELECT e.StaffNo AS [value]
            FROM WhitelistEmployee we
            INNER JOIN Employees e ON we.EmployeeId = e.EmployeeId
            WHERE we.DemandItemId = @DemandItemId AND we.IsActive = 1
            FOR JSON PATH
        );

        IF @WhitelistEmployeeIdsJson IS NOT NULL
            SET @WhitelistEmployeeIdsJson = REPLACE(REPLACE(@WhitelistEmployeeIdsJson, '{"value":"', '"'), '"}', '"');
        ELSE
            SET @WhitelistEmployeeIdsJson = '[]';

        DECLARE @BlacklistEmployeesJson NVARCHAR(MAX);
        SELECT @BlacklistEmployeesJson = (
            SELECT
                e.StaffNo AS employeeId,
                CONVERT(VARCHAR(10), be.StartDate, 23) AS blacklistStartDate,
                CONVERT(VARCHAR(10), be.EndDate, 23) AS blacklistEndDate
            FROM BlacklistEmployee be
            INNER JOIN Employees e ON be.EmployeeId = e.EmployeeId
            WHERE be.DemandItemId = @DemandItemId AND be.IsActive = 1
            FOR JSON PATH
        );

        IF @BlacklistEmployeesJson IS NULL
            SET @BlacklistEmployeesJson = '[]';

        --------------------------------------------------------------------
        -- 4) Requirements JSON (payload)
        --    Multi-rank support: Get ranks from DemandRequirementRank junction table
        --    Multi-scheme support: Get schemes from DemandRequirementScheme junction table
        --------------------------------------------------------------------
        DECLARE @RequirementsJson NVARCHAR(MAX);

        SELECT @RequirementsJson = (
            SELECT
                CAST(dr.DemandRequirementId AS NVARCHAR(20)) + '_' +
                CAST(ROW_NUMBER() OVER (PARTITION BY dr.DemandRequirementId ORDER BY drs.Id) AS NVARCHAR(10)) AS requirementId,
				50 AS icpmpBufferPercentage,
                pt.Code AS productTypeId,
                -- Multi-rank support: Get all ranks from junction table as JSON array
                JSON_QUERY(
                    ISNULL(
                        (
                            SELECT '[' + STRING_AGG(QUOTENAME(rk.RankCode, '"'), ',') + ']'
                            FROM DemandRequirementRank drr
                            INNER JOIN [Rank] rk ON drr.RankId = rk.RankId
                            WHERE drr.DemandRequirementId = dr.DemandRequirementId
                        ),
                        -- Fallback to legacy single rank if no junction table entries exist
                        '[' + QUOTENAME(r.RankCode, '"') + ']'
                    )
                ) AS rankIds,
                drs.Headcount AS headcount,
                (
                    SELECT
                        CASE LTRIM(RTRIM(value))
                            WHEN '0' THEN 'O'
                            -- For mixed shifts (e.g., ShiftCode='D,N'), use pattern number to index into shift codes
                            -- Pattern 1 -> 'D', Pattern 2 -> 'N', etc.
                            ELSE dbo.fn_GetShiftCodeByNumber(drs.ShiftCode, TRY_CAST(LTRIM(RTRIM(value)) AS INT))
                        END AS [value]
                    FROM STRING_SPLIT(ISNULL(srt.RotationPattern, ''), ',')
                    WHERE srt.RotationPattern IS NOT NULL
                    FOR JSON PATH
                ) AS workPattern,
                JSON_QUERY(dbo.fn_GetDemandRequiredQualificationsJson(@DemandItemId)) AS requiredQualifications,
                ISNULL(dr.Gender, 'Any') AS gender,
                -- Multi-scheme support: Get all schemes from junction table as JSON array
                -- If no schemes in junction table, check legacy single scheme, else output ["Any"]
                JSON_QUERY(
                    ISNULL(
                        NULLIF(
                            (
                                SELECT '[' + STRING_AGG(QUOTENAME(sch.SchemeName, '"'), ',') + ']'
                                FROM DemandRequirementScheme drs_sch
                                INNER JOIN EmployeeScheme sch ON drs_sch.EmployeeSchemeId = sch.EmployeeSchemeId
                                WHERE drs_sch.DemandRequirementId = dr.DemandRequirementId
                            ),
                            '[]'  -- NULLIF will return NULL if result is empty array string
                        ),
                        -- Fallback: check legacy single scheme, else "Any" for all schemes
                        CASE
                            WHEN es.SchemeName IS NOT NULL THEN '[' + QUOTENAME(es.SchemeName, '"') + ']'
                            ELSE '["Any"]'
                        END
                    )
                ) AS schemes,
				-- enableOtAwareIcpmp: true for demandBased, false for outcomeBased
				CAST(CASE WHEN @RosteringBasis = 'outcomeBased' THEN 0 ELSE 1 END AS BIT) AS [enableOtAwareIcpmp]
            FROM DemandRequirement dr
            INNER JOIN DemandRequirementShift drs
                ON dr.DemandRequirementId = drs.DemandRequirementId
            LEFT JOIN ProductType pt ON dr.ProductTypeId = pt.Id
            LEFT JOIN [Rank] r ON dr.RankId = r.RankId  -- Fallback for legacy single rank
            LEFT JOIN EmployeeScheme es ON dr.EmployeeSchemeId = es.EmployeeSchemeId  -- Fallback for legacy single scheme
            LEFT JOIN ShiftRotationTemplate srt ON drs.ShiftRotationTemplateId = srt.Id
            WHERE dr.DemandItemId = @DemandItemId
              AND dr.IsActive = 1
              AND drs.IsActive = 1
            ORDER BY dr.DemandRequirementId, drs.Id
            FOR JSON PATH
        );

        IF @RequirementsJson IS NULL
            SET @RequirementsJson = '[]';

        -- Preserve your original workPattern flattening behavior
        SET @RequirementsJson = REPLACE(REPLACE(@RequirementsJson, '"workPattern":[{"value":"', '"workPattern":["'), '"},{"value":"', '","');
        SET @RequirementsJson = REPLACE(@RequirementsJson, '"}],"requiredQualifications"', '"],"requiredQualifications"');

        --------------------------------------------------------------------
        -- 5) Build shifts object JSON (payload)
        --------------------------------------------------------------------
        DECLARE @ShiftsObjectJson NVARCHAR(MAX);

        SET @ShiftsObjectJson = CONCAT(
            '{',
                '"shiftDetails":', @ShiftDetailsJson, ',',
                '"includePublicHolidays":', CASE WHEN @IncludePublicHolidays = 1 THEN 'true' ELSE 'false' END, ',',
                '"includeEveOfPublicHolidays":', CASE WHEN @IncludeEveOfPublicHolidays = 1 THEN 'true' ELSE 'false' END, ',',
                '"shiftSetId":"Set_', REPLACE(@DemandCode, '-', '_'), '",',
                '"coverageDays":', @CoverageDaysJson, ',',
                '"coverageAnchor":"', CONVERT(VARCHAR(10), @StartDate, 23), '",',
                '"whitelist":{',
                    '"teamIds":', @WhitelistTeamIdsJson, ',',
                    '"employeeIds":', @WhitelistEmployeeIdsJson,
                '},',
                '"blacklist":{',
                    '"employeeIds":', @BlacklistEmployeesJson,
                '}',
            '}'
        );

        --------------------------------------------------------------------
        -- 6) Employee filtering (STAGED PIPELINE + WhitelistMode feature)
        --    Multi-rank support: Use DemandRequirementRank junction table for rank filtering
        --    Multi-scheme support: Use DemandRequirementScheme junction table for scheme filtering
        --------------------------------------------------------------------
        DECLARE @EmployeesJson NVARCHAR(MAX);

        -- Build requirement criteria for filtering (employee side)
        -- For ranks and schemes, we now use the junction tables
        CREATE TABLE #EmpRequirementCriteria (
            ProductTypeId INT NULL,
            Gender NVARCHAR(10) NULL
        );

        INSERT INTO #EmpRequirementCriteria (ProductTypeId, Gender)
        SELECT DISTINCT
            dr.ProductTypeId,
            dr.Gender
        FROM DemandRequirement dr
        WHERE dr.DemandItemId = @DemandItemId
          AND dr.IsActive = 1;

        -- Separate table for ranks from junction table (multi-rank support)
        CREATE TABLE #EmpRequirementRanks (
            RankId INT NOT NULL
        );

        -- Get all distinct ranks from the junction table for this demand's requirements
        INSERT INTO #EmpRequirementRanks (RankId)
        SELECT DISTINCT drr.RankId
        FROM DemandRequirementRank drr
        INNER JOIN DemandRequirement dr ON drr.DemandRequirementId = dr.DemandRequirementId
        WHERE dr.DemandItemId = @DemandItemId
          AND dr.IsActive = 1;

        -- Fallback: If no junction table entries exist, use legacy dr.RankId
        IF NOT EXISTS (SELECT 1 FROM #EmpRequirementRanks)
        BEGIN
            INSERT INTO #EmpRequirementRanks (RankId)
            SELECT DISTINCT dr.RankId
            FROM DemandRequirement dr
            WHERE dr.DemandItemId = @DemandItemId
              AND dr.IsActive = 1
              AND dr.RankId IS NOT NULL;
        END

        -- Separate table for schemes from junction table (multi-scheme support)
        CREATE TABLE #EmpRequirementSchemes (
            EmployeeSchemeId INT NOT NULL
        );

        -- Get all distinct schemes from the junction table for this demand's requirements
        INSERT INTO #EmpRequirementSchemes (EmployeeSchemeId)
        SELECT DISTINCT drs_sch.EmployeeSchemeId
        FROM DemandRequirementScheme drs_sch
        INNER JOIN DemandRequirement dr ON drs_sch.DemandRequirementId = dr.DemandRequirementId
        WHERE dr.DemandItemId = @DemandItemId
          AND dr.IsActive = 1;

        -- Fallback: If no junction table entries exist, use legacy dr.EmployeeSchemeId
        IF NOT EXISTS (SELECT 1 FROM #EmpRequirementSchemes)
        BEGIN
            INSERT INTO #EmpRequirementSchemes (EmployeeSchemeId)
            SELECT DISTINCT dr.EmployeeSchemeId
            FROM DemandRequirement dr
            WHERE dr.DemandItemId = @DemandItemId
              AND dr.IsActive = 1
              AND dr.EmployeeSchemeId IS NOT NULL;
        END

        DECLARE @HasProductTypeFilter BIT = 0;
        DECLARE @HasRankFilter BIT = 0;
        DECLARE @HasSchemeFilter BIT = 0;
        DECLARE @HasGenderFilter BIT = 0;

        IF EXISTS (SELECT 1 FROM #EmpRequirementCriteria WHERE ProductTypeId IS NOT NULL) SET @HasProductTypeFilter = 1;
        IF EXISTS (SELECT 1 FROM #EmpRequirementRanks) SET @HasRankFilter = 1;
        -- Scheme filter only applies if there are specific schemes (empty = "Any" = no filter)
        IF EXISTS (SELECT 1 FROM #EmpRequirementSchemes) SET @HasSchemeFilter = 1;
        IF EXISTS (SELECT 1 FROM #EmpRequirementCriteria WHERE Gender IS NOT NULL AND Gender != 'Any') SET @HasGenderFilter = 1;

        -- Separate table for demand's required qualifications
        -- Parse from ALL groups returned by fn_GetDemandRequiredQualificationsJson
        -- Format: "ConstraintCode_ConstraintName" (e.g., "523_BASIC_AVIATION_SECURITY_COURSE")
        CREATE TABLE #DemandRequiredQualifications (
            QualificationCode NVARCHAR(200) NOT NULL PRIMARY KEY
        );

        -- Get the JSON from the function that generates requiredQualifications
        DECLARE @RequiredQualificationsJson NVARCHAR(MAX);
        SET @RequiredQualificationsJson = dbo.fn_GetDemandRequiredQualificationsJson(@DemandItemId);

        -- Parse all qualifications from all groups (groupId, matchType don't matter for filtering)
        -- We just need the flat list of all qualification codes that could be required
        IF @RequiredQualificationsJson IS NOT NULL 
           AND @RequiredQualificationsJson != '[]'
           AND @RequiredQualificationsJson != ''
           AND ISJSON(@RequiredQualificationsJson) = 1
        BEGIN
            INSERT INTO #DemandRequiredQualifications (QualificationCode)
            SELECT DISTINCT LTRIM(RTRIM(qual.value))
            FROM OPENJSON(@RequiredQualificationsJson) AS groups
            CROSS APPLY OPENJSON(groups.value, '$.qualifications') AS qual
            WHERE qual.value IS NOT NULL
              AND qual.value != '';
        END
        ELSE IF @RequiredQualificationsJson IS NOT NULL AND ISJSON(@RequiredQualificationsJson) = 0
        BEGIN
            PRINT 'WARNING: fn_GetDemandRequiredQualificationsJson returned invalid JSON: ' + 
                  ISNULL(LEFT(@RequiredQualificationsJson, 100), 'NULL');
        END

        DECLARE @HasQualificationFilter BIT = 0;
        IF EXISTS (SELECT 1 FROM #DemandRequiredQualifications) SET @HasQualificationFilter = 1;

        PRINT 'Employee filtering - HasProductTypeFilter: ' + CAST(@HasProductTypeFilter AS NVARCHAR(1)) +
              ', HasRankFilter: ' + CAST(@HasRankFilter AS NVARCHAR(1)) +
              ', HasSchemeFilter: ' + CAST(@HasSchemeFilter AS NVARCHAR(1)) +
              ', HasGenderFilter: ' + CAST(@HasGenderFilter AS NVARCHAR(1)) +
              ', HasQualificationFilter: ' + CAST(@HasQualificationFilter AS NVARCHAR(1));
        PRINT 'RosterFlexibility: ' + @RosterFlexibility;
        PRINT 'WhitelistMode: ' + @WhitelistMode;

        -- A) Base employees
        CREATE TABLE #EmpBaseEmployees (
            EmployeeId INT NOT NULL PRIMARY KEY,
            StaffNo NVARCHAR(20) NOT NULL,
            OrgUnitId BIGINT NULL,
            ProductTypeId INT NULL,
            RankId INT NULL,
            EmployeeSchemeId INT NULL,
            Gender NVARCHAR(10) NULL
        );

        INSERT INTO #EmpBaseEmployees (EmployeeId, StaffNo, OrgUnitId, ProductTypeId, RankId, EmployeeSchemeId, Gender)
        SELECT
            e.EmployeeId,
            e.StaffNo,
            e.OrgUnitId,
            e.ProductTypeId,
            e.RankId,
            e.EmployeeSchemeId,
            e.Gender
        FROM Employees e
        WHERE e.IsActive = 1;

        -- B) Whitelisted employees (orgunit + team + direct employee)
        CREATE TABLE #EmpWhitelistedEmployees (
            EmployeeId INT NOT NULL PRIMARY KEY
        );

        -- B.1) Employees from WhitelistOrgUnit
        INSERT INTO #EmpWhitelistedEmployees (EmployeeId)
        SELECT DISTINCT e.EmployeeId
        FROM WhitelistOrgUnit wo
        INNER JOIN Employees e ON e.OrgUnitId = wo.OrgUnitId
        WHERE wo.DemandItemId = @DemandItemId
          AND wo.IsActive = 1
          AND e.IsActive = 1;

        -- B.2) Employees from WhitelistTeam
        INSERT INTO #EmpWhitelistedEmployees (EmployeeId)
        SELECT DISTINCT tm.EmployeeId
        FROM WhitelistTeam wt
        INNER JOIN TeamMembership tm ON wt.TeamId = tm.TeamId
        WHERE wt.DemandItemId = @DemandItemId
          AND wt.IsActive = 1
          AND (tm.EndDate IS NULL OR tm.EndDate > GETDATE())
          AND NOT EXISTS (SELECT 1 FROM #EmpWhitelistedEmployees w WHERE w.EmployeeId = tm.EmployeeId);

        -- B.3) Employees from WhitelistEmployee (direct)
        INSERT INTO #EmpWhitelistedEmployees (EmployeeId)
        SELECT we.EmployeeId
        FROM WhitelistEmployee we
        WHERE we.DemandItemId = @DemandItemId
          AND we.IsActive = 1
          AND NOT EXISTS (SELECT 1 FROM #EmpWhitelistedEmployees w WHERE w.EmployeeId = we.EmployeeId);

        DECLARE @HasWhitelist BIT = IIF(EXISTS (SELECT 1 FROM #EmpWhitelistedEmployees), 1, 0);

        -- C) Candidate pool:
        --    - INCLUSIVE mode: OrgUnit baseline + whitelisted employees
        --    - STRICT mode: Only whitelisted employees (no OrgUnit baseline)
        CREATE TABLE #EmpCandidateEmployees (
            EmployeeId INT NOT NULL PRIMARY KEY
        );

        IF @WhitelistMode = 'INCLUSIVE'
        BEGIN
            -- INCLUSIVE (demandBased): Start with OrgUnit baseline
            INSERT INTO #EmpCandidateEmployees (EmployeeId)
            SELECT be.EmployeeId
            FROM #EmpBaseEmployees be
            WHERE be.OrgUnitId = @OrgUnitId;

            -- INCLUSIVE: Also add whitelisted (even if outside OrgUnit)
            INSERT INTO #EmpCandidateEmployees (EmployeeId)
            SELECT w.EmployeeId
            FROM #EmpWhitelistedEmployees w
            WHERE NOT EXISTS (SELECT 1 FROM #EmpCandidateEmployees c WHERE c.EmployeeId = w.EmployeeId);
        END
        ELSE
        BEGIN
            -- STRICT (outcomeBased): Only whitelisted employees
            -- (WhitelistOrgUnit + WhitelistTeam + WhitelistEmployee)
            INSERT INTO #EmpCandidateEmployees (EmployeeId)
            SELECT w.EmployeeId
            FROM #EmpWhitelistedEmployees w;
        END

        DECLARE @CandidateCount INT = (SELECT COUNT(*) FROM #EmpCandidateEmployees);
        PRINT 'Candidate employees (' + @WhitelistMode + ' mode): ' + CAST(@CandidateCount AS NVARCHAR(20));

        -- D) Final pool: Apply requirement filters to candidates
        --    - STRICT mode (outcomeBased): Whitelisted employees BYPASS requirement filters
        --      (explicit whitelist = user wants these specific employees regardless of criteria)
        --    - INCLUSIVE mode (demandBased): ALL employees (including whitelisted) must match requirement filters
        --      (ensures only qualified employees are rostered)
        CREATE TABLE #EmpFinalEmployees (
            EmployeeId INT NOT NULL PRIMARY KEY
        );

        -- D.1) For STRICT mode (outcomeBased): Add whitelisted employees (bypass requirement filters)
        -- In outcomeBased, whitelist is an explicit override - user specifically selected these employees
        IF @WhitelistMode = 'STRICT'
        BEGIN
            INSERT INTO #EmpFinalEmployees (EmployeeId)
            SELECT be.EmployeeId
            FROM #EmpBaseEmployees be
            INNER JOIN #EmpWhitelistedEmployees w ON w.EmployeeId = be.EmployeeId;

            DECLARE @WhitelistAddedCount INT = @@ROWCOUNT;
            PRINT 'Added ' + CAST(@WhitelistAddedCount AS NVARCHAR(20)) + ' whitelisted employees (STRICT mode - bypass requirement filters)';
        END

        -- D.2) For INCLUSIVE mode (demandBased): Add ALL candidates that match requirement filters
        -- This includes both whitelisted and non-whitelisted - all must meet requirements
        IF @WhitelistMode = 'INCLUSIVE'
        BEGIN
            INSERT INTO #EmpFinalEmployees (EmployeeId)
            SELECT be.EmployeeId
            FROM #EmpBaseEmployees be
            INNER JOIN #EmpCandidateEmployees c ON c.EmployeeId = be.EmployeeId
            WHERE (
                    @HasProductTypeFilter = 0
                    OR be.ProductTypeId IN (SELECT ProductTypeId FROM #EmpRequirementCriteria WHERE ProductTypeId IS NOT NULL)
                  )
              AND (
                    @HasRankFilter = 0
                    OR be.RankId IN (SELECT RankId FROM #EmpRequirementRanks)
                  )
              AND (
                    @HasSchemeFilter = 0
                    OR be.EmployeeSchemeId IN (SELECT EmployeeSchemeId FROM #EmpRequirementSchemes)
                  )
              AND (
                    @HasGenderFilter = 0
                    OR be.Gender IN (SELECT Gender FROM #EmpRequirementCriteria WHERE Gender IS NOT NULL AND Gender != 'Any')
                  )
              AND (
                    -- Qualification filter: Employee must have at least 1 valid qualification
                    -- that matches the demand's required qualifications
                    @HasQualificationFilter = 0
                    OR EXISTS (
                        SELECT 1
                        FROM vw_EmployeeValidQualifications evq
                        WHERE evq.StaffNo = be.StaffNo
                          AND evq.ValidFrom <= @StartDate
                          AND evq.ValidTo >= @StartDate
                          AND REPLACE(evq.ConstraintCode + '_' + ISNULL(evq.ConstraintName, ''), ' ', '_')
                              IN (SELECT QualificationCode FROM #DemandRequiredQualifications)
                    )
                  );

            DECLARE @FilteredAddedCount INT = @@ROWCOUNT;
            PRINT 'Added ' + CAST(@FilteredAddedCount AS NVARCHAR(20)) + ' employees (INCLUSIVE mode - all must match requirement filters)';
        END

        DECLARE @FinalBeforeExcl INT = (SELECT COUNT(*) FROM #EmpFinalEmployees);
        PRINT 'Final employees before exclusions: ' + CAST(@FinalBeforeExcl AS NVARCHAR(20));

        -- E) Exclude blacklisted (date-aware)
        DELETE f
        FROM #EmpFinalEmployees f
        WHERE EXISTS (
            SELECT 1
            FROM BlacklistEmployee be
            WHERE be.DemandItemId = @DemandItemId
              AND be.IsActive = 1
              AND be.EmployeeId = f.EmployeeId
              AND (be.StartDate IS NULL OR be.StartDate <= @StartDate)
              AND (be.EndDate   IS NULL OR be.EndDate   >= @StartDate)
        );

        DECLARE @AfterBlacklistCount INT = (SELECT COUNT(*) FROM #EmpFinalEmployees);
        PRINT 'Employees after demand-level blacklist: ' + CAST(@AfterBlacklistCount AS NVARCHAR(20));

        -- E.2) Exclude employees from GlobalBlacklist (scope-based: OrgUnit, Customer, Site, Sector)
        -- Note: Inlined here instead of calling usp_GetGlobalBlacklistedEmployees due to SQL Server
        -- limitation: "An INSERT EXEC statement cannot be nested" (this proc is called via INSERT EXEC
        -- from usp_BuildSolverJson). For standalone debugging, use usp_GetGlobalBlacklistedEmployees directly.

        -- Get additional demand context for scope matching
        DECLARE @GBL_CustomerId BIGINT;
        DECLARE @GBL_SiteId INT;
        DECLARE @GBL_SectorId INT;
        DECLARE @GBL_BusinessUnitId INT;

        SELECT
            @GBL_CustomerId = wi.CustomerInfoId,
            @GBL_SiteId = l.SiteId,
            @GBL_SectorId = null,
            @GBL_BusinessUnitId = ou.BusinessUnitId
        FROM WorkItem wi
        INNER JOIN OrgUnit ou ON wi.OrgUnitId = ou.OrgUnitId
        LEFT JOIN Location l ON l.LocationId = @LocationId
        LEFT JOIN Site st ON l.SiteId = st.SiteId
        WHERE wi.Id = @WorkItemId;

        -- Delete employees that match any active GlobalBlacklist entry
        DELETE f
        FROM #EmpFinalEmployees f
        WHERE EXISTS (
            SELECT 1
            FROM GlobalBlacklist gb
            WHERE gb.EmployeeId = f.EmployeeId
              AND gb.IsActive = 1
              AND gb.BusinessUnitId = @GBL_BusinessUnitId
              AND (gb.StartDate IS NULL OR CAST(gb.StartDate AS DATE) <= @StartDate)
              AND (gb.EndDate IS NULL OR CAST(gb.EndDate AS DATE) >= @StartDate)
              AND (
                  -- Case 1: Global blacklist (no scopes = blocks everywhere)
                  NOT EXISTS (
                      SELECT 1 FROM GlobalBlacklistScope gbs WHERE gbs.GlobalBlacklistId = gb.Id
                  )
                  OR
                  -- Case 2: Scoped blacklist - ALL scopes must match
                  NOT EXISTS (
                      SELECT 1
                      FROM GlobalBlacklistScope gbs
                      INNER JOIN BlacklistScopeType bst ON gbs.ScopeTypeId = bst.Id
                      WHERE gbs.GlobalBlacklistId = gb.Id
                        -- Find any scope that does NOT match (if none found, all match)
                        AND NOT (
                            (bst.Code = 'OrgUnit' AND TRY_CAST(gbs.ScopeValue AS BIGINT) = @OrgUnitId)
                            OR (bst.Code = 'Customer' AND TRY_CAST(gbs.ScopeValue AS BIGINT) = @GBL_CustomerId)
                            OR (bst.Code = 'Site' AND TRY_CAST(gbs.ScopeValue AS INT) = @GBL_SiteId)
                            OR (bst.Code = 'Sector' AND TRY_CAST(gbs.ScopeValue AS INT) = @GBL_SectorId)
                        )
                  )
              )
        );

        DECLARE @AfterGlobalBlacklistCount INT = (SELECT COUNT(*) FROM #EmpFinalEmployees);
        PRINT 'Employees after global blacklist: ' + CAST(@AfterGlobalBlacklistCount AS NVARCHAR(20));

        -- F) Build unavailability dates for employees
        -- Sources of unavailability:
        --   1. Assignments to OTHER demands (working shifts)
        --   2. OFF_DAY/REST status from EmployeeDailyRoster (scheduled rest days)
        --   3. Approved leave requests from LeaveRequest table
        --   4. Offboarding dates (DateOfLeaving onwards for employees leaving during roster period)
        -- This allows the same employee to be rostered on different dates across multiple demands

        CREATE TABLE #EmployeeUnavailability (
            EmployeeId INT,
            UnavailableDate DATE,
            PRIMARY KEY (EmployeeId, UnavailableDate)
        );

        IF @RosterFlexibility = 'newOfficers'
        BEGIN
            -- For newOfficers: ALL existing assignments make dates unavailable
            INSERT INTO #EmployeeUnavailability (EmployeeId, UnavailableDate)
            SELECT DISTINCT f.EmployeeId, ss.ShiftDate
            FROM #EmpFinalEmployees f
            INNER JOIN ShiftAssignment sa ON sa.EmployeeId = f.EmployeeId AND sa.IsActive = 1
            INNER JOIN ShiftSlot ss ON sa.ShiftSlotId = ss.ShiftSlotId AND ss.IsActive = 1
            WHERE ss.ShiftDate BETWEEN @StartDate AND @EndDate;
        END
        ELSE IF @RosterFlexibility IN ('fullRoster', 'reRoster')
        BEGIN
            -- For fullRoster/reRoster: Only assignments to OTHER demands make dates unavailable
            -- (assignments to THIS demand will be cleared before rostering)
            INSERT INTO #EmployeeUnavailability (EmployeeId, UnavailableDate)
            SELECT DISTINCT f.EmployeeId, ss.ShiftDate
            FROM #EmpFinalEmployees f
            INNER JOIN ShiftAssignment sa ON sa.EmployeeId = f.EmployeeId AND sa.IsActive = 1
            INNER JOIN ShiftSlot ss ON sa.ShiftSlotId = ss.ShiftSlotId AND ss.IsActive = 1
            INNER JOIN RosterDemand rd ON ss.RosterDemandId = rd.RosterDemandId
            WHERE ss.ShiftDate BETWEEN @StartDate AND @EndDate
              AND rd.DemandId != @DemandItemId;  -- Only OTHER demands
        END
        ELSE
        BEGIN
            RAISERROR('Invalid @RosterFlexibility value: %s', 16, 1, @RosterFlexibility);
            RETURN;
        END

        -- F.2) Also add OFF_DAY dates from EmployeeDailyRoster
        -- These are scheduled rest days - employee should not be assigned to any demand on these dates
        INSERT INTO #EmployeeUnavailability (EmployeeId, UnavailableDate)
        SELECT DISTINCT f.EmployeeId, edr.RosterDate
        FROM #EmpFinalEmployees f
        INNER JOIN EmployeeDailyRoster edr ON edr.EmployeeId = f.EmployeeId AND edr.IsActive = 1
        WHERE edr.RosterDate BETWEEN @StartDate AND @EndDate
          AND edr.DailyStatus IN ('OFF_DAY', 'REST')
          AND NOT EXISTS (
              SELECT 1 FROM #EmployeeUnavailability eu
              WHERE eu.EmployeeId = f.EmployeeId AND eu.UnavailableDate = edr.RosterDate
          );

        -- F.3) Add approved leave request dates
        -- Employees on approved leave should not be assigned to any demand on those dates
        -- Use recursive CTE to generate all dates between leave StartDate and EndDate
        ;WITH LeaveDates AS (
            -- Base case: Start with leave start date
            SELECT
                f.EmployeeId,
                CAST(lr.StartDate AS DATE) AS LeaveDate,
                CAST(lr.EndDate AS DATE) AS LeaveEndDate
            FROM #EmpFinalEmployees f
            INNER JOIN LeaveRequest lr ON lr.EmployeeId = f.EmployeeId
            WHERE lr.Status = 'Approved'
              AND CAST(lr.StartDate AS DATE) <= @EndDate
              AND CAST(lr.EndDate AS DATE) >= @StartDate

            UNION ALL

            -- Recursive case: Add one day until EndDate
            SELECT
                EmployeeId,
                DATEADD(DAY, 1, LeaveDate),
                LeaveEndDate
            FROM LeaveDates
            WHERE LeaveDate < LeaveEndDate
        )
        INSERT INTO #EmployeeUnavailability (EmployeeId, UnavailableDate)
        SELECT DISTINCT EmployeeId, LeaveDate
        FROM LeaveDates
        WHERE LeaveDate BETWEEN @StartDate AND @EndDate
          AND NOT EXISTS (
              SELECT 1 FROM #EmployeeUnavailability eu
              WHERE eu.EmployeeId = LeaveDates.EmployeeId AND eu.UnavailableDate = LeaveDates.LeaveDate
          )
        OPTION (MAXRECURSION 366);  -- Allow up to 1 year of leave

        DECLARE @LeaveUnavailabilityCount INT = @@ROWCOUNT;
        PRINT 'Added ' + CAST(@LeaveUnavailabilityCount AS NVARCHAR(20)) + ' unavailability dates from approved leave requests';

        -- F.4) Add offboarding dates - employees leaving during the roster period
        -- Mark all dates from DateOfLeaving onwards as unavailable
        ;WITH OffboardDates AS (
            -- Base case: Start with DateOfLeaving
            SELECT
                f.EmployeeId,
                CAST(e.DateOfLeaving AS DATE) AS OffboardDate
            FROM #EmpFinalEmployees f
            INNER JOIN Employees e ON e.EmployeeId = f.EmployeeId
            WHERE e.DateOfLeaving IS NOT NULL
              AND CAST(e.DateOfLeaving AS DATE) BETWEEN @StartDate AND @EndDate

            UNION ALL

            -- Recursive case: Add one day until EndDate
            SELECT
                EmployeeId,
                DATEADD(DAY, 1, OffboardDate)
            FROM OffboardDates
            WHERE OffboardDate < @EndDate
        )
        INSERT INTO #EmployeeUnavailability (EmployeeId, UnavailableDate)
        SELECT DISTINCT EmployeeId, OffboardDate
        FROM OffboardDates
        WHERE OffboardDate BETWEEN @StartDate AND @EndDate
          AND NOT EXISTS (
              SELECT 1 FROM #EmployeeUnavailability eu
              WHERE eu.EmployeeId = OffboardDates.EmployeeId AND eu.UnavailableDate = OffboardDates.OffboardDate
          )
        OPTION (MAXRECURSION 366);

        DECLARE @OffboardUnavailabilityCount INT = @@ROWCOUNT;
        PRINT 'Added ' + CAST(@OffboardUnavailabilityCount AS NVARCHAR(20)) + ' unavailability dates from employee offboarding';

        DECLARE @UnavailabilityCount INT = (SELECT COUNT(*) FROM #EmployeeUnavailability);
        PRINT 'Built ' + CAST(@UnavailabilityCount AS NVARCHAR(20)) + ' employee unavailability date records';

        DECLARE @AfterRosterCount INT = (SELECT COUNT(*) FROM #EmpFinalEmployees);
        PRINT 'Employees after roster conflict stage: ' + CAST(@AfterRosterCount AS NVARCHAR(20)) + ' (no longer excluded, unavailability tracked instead)';

        --------------------------------------------------------------------
        -- 6.G) Build Employees JSON from final set
        -- Include unavailability dates from #EmployeeUnavailability
        -- When team whitelisting is used, use TeamCode as ouId instead of OrgUnit SAP_OrgCode
        -- Qualifications: Only include qualifications that match demand's required qualifications
        --------------------------------------------------------------------
        DECLARE @IsTeamBasedWhitelist BIT = 0;
        IF @WhitelistTeamIdsJson <> '[]'
            SET @IsTeamBasedWhitelist = 1;

        SELECT @EmployeesJson = (
            SELECT
                e.StaffNo AS employeeId,
                -- Use TeamCode as ouId when team-based whitelisting, else use OrgUnit SAP_OrgCode
                CASE
                    WHEN @IsTeamBasedWhitelist = 1 THEN t.TeamCode
                    ELSE orgU.SAP_OrgCode
                END AS ouId,
                pt.Code AS productTypeId,
                r.RankCode AS rankId,
                ISNULL(es.SchemeName, 'Global') AS [scheme],
                -- RotationOffset: Look up SeqStart from whitelist tables (Employee > Team > OrgUnit)
                -- SeqStart is 1-based in DB, solver expects 0-based offset
                CASE
                    -- Priority 1: Direct WhitelistEmployee.SeqStart
                    WHEN we.SeqStart IS NOT NULL AND we.SeqStart > 0 THEN we.SeqStart - 1
                    -- Priority 2: WhitelistTeam.SeqStart (via team membership)
                    WHEN wt.SeqStart IS NOT NULL AND wt.SeqStart > 0 THEN wt.SeqStart - 1
                    -- Priority 3: WhitelistOrgUnit.SeqStart (via employee's OrgUnit)
                    WHEN wo.SeqStart IS NOT NULL AND wo.SeqStart > 0 THEN wo.SeqStart - 1
                    -- Default: 0
                    ELSE 0
                END AS rotationOffset,
                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM vw_EmployeeConstraintDetails ecd
                        WHERE ecd.StaffNo = e.StaffNo
                          AND ecd.ConstraintCode = 'NRIC'
                          AND ecd.ConstraintValue = '1'
                          AND ecd.IsActive = 1
                    ) THEN 1
                    ELSE 0
                END AS [local],
                ISNULL(e.Gender, 'M') AS gender,
                -- Qualifications: Only include those that match demand's required qualifications
                -- If no qualification filter, return empty array (no qualifications needed for this demand)
                JSON_QUERY(
                    CASE
                        WHEN @HasQualificationFilter = 0 THEN '[]'
                        ELSE ISNULL((
                            SELECT
                                REPLACE(evq.ConstraintCode + '_' + ISNULL(evq.ConstraintName, ''), ' ', '_') AS code,
                                CONVERT(VARCHAR(10), evq.ValidFrom, 23) AS validFrom,
                                CONVERT(VARCHAR(10), evq.ValidTo, 23) AS expiryDate
                            FROM vw_EmployeeValidQualifications evq
                            WHERE evq.StaffNo = e.StaffNo
                              AND evq.ValidFrom <= @StartDate
                              AND evq.ValidTo >= @StartDate
                              -- Only include qualifications that match demand's requirements
                              AND REPLACE(evq.ConstraintCode + '_' + ISNULL(evq.ConstraintName, ''), ' ', '_')
                                  IN (SELECT QualificationCode FROM #DemandRequiredQualifications)
                            ORDER BY evq.ConstraintCode, evq.ConstraintName
                            FOR JSON PATH
                        ), '[]')
                    END
                ) AS qualifications,
                JSON_QUERY('{}') AS preferences,
                -- Build unavailability as simple date string array ["2026-01-05", "2026-01-06"]
                JSON_QUERY(ISNULL((
                    SELECT '[' + STRING_AGG('"' + CONVERT(VARCHAR(10), eu.UnavailableDate, 23) + '"', ',') WITHIN GROUP (ORDER BY eu.UnavailableDate) + ']'
                    FROM #EmployeeUnavailability eu
                    WHERE eu.EmployeeId = e.EmployeeId
                ), '[]')) AS unavailability
            FROM #EmpFinalEmployees finalSet
            INNER JOIN Employees e ON e.EmployeeId = finalSet.EmployeeId
            INNER JOIN OrgUnit orgU ON e.OrgUnitId = orgU.OrgUnitID
            -- Get team via TeamMembership (employee may belong to multiple teams, use active one)
            LEFT JOIN TeamMembership tm ON tm.EmployeeId = e.EmployeeId
                AND (tm.EndDate IS NULL OR tm.EndDate > GETDATE())
            LEFT JOIN Team t ON tm.TeamId = t.TeamID
            -- Whitelist tables for SeqStart (rotation offset) lookup
            LEFT JOIN WhitelistEmployee we ON we.EmployeeId = e.EmployeeId
                AND we.DemandItemId = @DemandItemId AND we.IsActive = 1
            LEFT JOIN WhitelistTeam wt ON wt.TeamId = tm.TeamId
                AND wt.DemandItemId = @DemandItemId AND wt.IsActive = 1
            LEFT JOIN WhitelistOrgUnit wo ON wo.OrgUnitId = e.OrgUnitId
                AND wo.DemandItemId = @DemandItemId AND wo.IsActive = 1
            -- Note: WhitelistOrgUnit filtering already done in pipeline steps B/C.
            -- Removed redundant INNER JOIN that was excluding valid employees.
            LEFT JOIN ProductType pt ON e.ProductTypeId = pt.Id
            LEFT JOIN [Rank] r ON e.RankId = r.RankId
            LEFT JOIN EmployeeScheme es ON e.EmployeeSchemeId = es.EmployeeSchemeId
            FOR JSON PATH
        );

        DROP TABLE #EmployeeUnavailability;

        IF @EmployeesJson IS NULL
            SET @EmployeesJson = '[]';

        DECLARE @EmployeeCount INT;
        SELECT @EmployeeCount = COUNT(*) FROM OPENJSON(@EmployeesJson);
        PRINT 'Selected ' + CAST(@EmployeeCount AS NVARCHAR(20)) + ' employees after full filtering';

        --------------------------------------------------------------------
        -- 7) Build demand item JSON
        --------------------------------------------------------------------
        DECLARE @DemandItemJson NVARCHAR(MAX);

        SET @DemandItemJson = CONCAT(
            '{',
                '"demandId":"', @DemandCode, '",',
                '"locationId":"', ISNULL(@LocationCode, ''), '",',
                '"shiftStartDate":"', CONVERT(VARCHAR(10), @StartDate, 23), '",',
                '"rosteringBasis":"', @RosteringBasis, '",',
                '"minStaffThresholdPercentage":', CAST(@MinStaffThresholdPercentage AS NVARCHAR(10)), ',',
                '"shifts":[', @ShiftsObjectJson, '],',
                '"requirements":', @RequirementsJson,
            '}'
        );

		-- '"ouId":"', ISNULL(@OrgUnitCode, ''), '",',

        --------------------------------------------------------------------
        -- 8) Build ouOffsets JSON from WhitelistOrgUnit (using SeqStart as rotationOffset)
        --------------------------------------------------------------------
        DECLARE @OuOffsetsJson NVARCHAR(MAX);

        SELECT @OuOffsetsJson = (
            SELECT
                t.SAP_OrgCode AS ouId,
                -- SeqStart is 1-based in DB, solver expects 0-based offset
                -- If SeqStart > 0, subtract 1; if 0 or NULL, keep as 0
                CASE
                    WHEN ISNULL(wt.SeqStart, 0) > 0 THEN wt.SeqStart - 1
                    ELSE 0
                END AS rotationOffset
            FROM WhitelistOrgUnit wt
            INNER JOIN OrgUnit t ON wt.OrgUnitId = t.OrgUnitID
            WHERE wt.DemandItemId = @DemandItemId
              AND wt.IsActive = 1
            FOR JSON PATH
        );

        IF @OuOffsetsJson IS NULL
            SET @OuOffsetsJson = '[]';

        --------------------------------------------------------------------
        -- 8b) Build team-based ouOffsets JSON from WhitelistTeam (using TeamCode as ouId)
        --------------------------------------------------------------------
        DECLARE @TeamOffsetsJson NVARCHAR(MAX);

        SELECT @TeamOffsetsJson = (
            SELECT
                t.TeamCode AS ouId,  -- Use TeamCode as ouId for team-based whitelisting
                -- SeqStart is 1-based in DB, solver expects 0-based offset
                -- If SeqStart > 0, subtract 1; if 0 or NULL, keep as 0
                CASE
                    WHEN ISNULL(wt.SeqStart, 0) > 0 THEN wt.SeqStart - 1
                    ELSE 0
                END AS rotationOffset
            FROM WhitelistTeam wt
            INNER JOIN Team t ON wt.TeamId = t.TeamID
            WHERE wt.DemandItemId = @DemandItemId
              AND wt.IsActive = 1
            FOR JSON PATH
        );

        IF @TeamOffsetsJson IS NULL
            SET @TeamOffsetsJson = '[]';

        --------------------------------------------------------------------
        -- 8c) Build employee-based ouOffsets from WhitelistEmployee
        -- Only when outcomeBased (fixedRotationOffset = "ouOffsets")
        -- Get distinct org units from whitelisted employees with rotationOffset: 0
        --------------------------------------------------------------------
        DECLARE @EmpOuOffsetsJson NVARCHAR(MAX);

        IF @RosteringBasis = 'outcomeBased'
        BEGIN
            SELECT @EmpOuOffsetsJson = (
                SELECT DISTINCT
                    ou.SAP_OrgCode AS ouId,
                    0 AS rotationOffset  -- Default offset for employee-derived org units
                FROM WhitelistEmployee we
                INNER JOIN Employees e ON we.EmployeeId = e.EmployeeId
                INNER JOIN OrgUnit ou ON e.OrgUnitId = ou.OrgUnitID
                WHERE we.DemandItemId = @DemandItemId
                  AND we.IsActive = 1
                  AND e.IsActive = 1
                FOR JSON PATH
            );
        END

        IF @EmpOuOffsetsJson IS NULL
            SET @EmpOuOffsetsJson = '[]';

        --------------------------------------------------------------------
        -- 8d) Determine which offsets to use (OrgUnit-based, Team-based, or Employee-derived)
        -- Priority: Team > OrgUnit > Employee-derived
        -- Since demand uses either one, we pick the non-empty one
        --------------------------------------------------------------------
        DECLARE @FinalOffsetsJson NVARCHAR(MAX);

        IF @TeamOffsetsJson <> '[]'
            SET @FinalOffsetsJson = @TeamOffsetsJson;
        ELSE IF @OuOffsetsJson <> '[]'
            SET @FinalOffsetsJson = @OuOffsetsJson;
        ELSE
            SET @FinalOffsetsJson = @EmpOuOffsetsJson;

        --------------------------------------------------------------------
        -- 9) Final JSON
        --------------------------------------------------------------------
        DECLARE @ResultJson NVARCHAR(MAX);

        SET @ResultJson = CONCAT(
            '{',
                '"ouOffsets":', @FinalOffsetsJson, ',',
                '"demandItems":[', @DemandItemJson, '],',
                '"employees":', @EmployeesJson,
            '}'
        );

        SELECT @ResultJson AS SolverJson;

        --------------------------------------------------------------------
        -- Cleanup
        --------------------------------------------------------------------
        DROP TABLE IF EXISTS #EmpFinalEmployees;
        DROP TABLE IF EXISTS #EmpCandidateEmployees;
        DROP TABLE IF EXISTS #EmpWhitelistedEmployees;
        DROP TABLE IF EXISTS #EmpBaseEmployees;
        DROP TABLE IF EXISTS #EmpRequirementCriteria;
        DROP TABLE IF EXISTS #EmpRequirementRanks;
        DROP TABLE IF EXISTS #EmpRequirementSchemes;
        DROP TABLE IF EXISTS #DemandRequiredQualifications;

    END TRY
    BEGIN CATCH
        DECLARE @ErrMsg NVARCHAR(4000) = ERROR_MESSAGE();
        DECLARE @ErrSeverity INT = ERROR_SEVERITY();
        DECLARE @ErrState INT = ERROR_STATE();
        RAISERROR(@ErrMsg, @ErrSeverity, @ErrState);
        RETURN;
    END CATCH
END
