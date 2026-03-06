# Task 4 — T-SQL: usp_VehiclePart_ReadSearch Optimisation

## Files

| File | Description |
|------|-------------|
| `usp_VehiclePart_ReadSearch.sql` | Updated stored procedure |
| `Index_table_changes.sql` | Schema changes: PKs, FK, indexes, constraints |

Run `Index_table_changes.sql` first, then `usp_VehiclePart_ReadSearch.sql`.

---

## Schema Changes (`Index_table_changes.sql`)

### 1. Primary Keys added to both tables

```sql
ALTER TABLE Vehicle     ADD CONSTRAINT PK_Vehicle     PRIMARY KEY CLUSTERED (VehicleID);
ALTER TABLE VehiclePart ADD CONSTRAINT PK_VehiclePart PRIMARY KEY CLUSTERED (VehiclePartID);
```

**Justification:** Neither table had a primary key in the original DDL. Without a clustered index, SQL Server creates a heap — every join and lookup requires a full table scan. Clustered PKs give each table a physical sort order, make joins on `VehicleID` and lookups by `VehiclePartID` significantly faster, and are a baseline requirement for any table with referential integrity.

---

### 2. NOT NULL constraints and column widths widened

```sql
ALTER TABLE Vehicle     ALTER COLUMN VehicleName     nvarchar(50)  NOT NULL;
ALTER TABLE VehiclePart ALTER COLUMN VehiclePartName nvarchar(100) NOT NULL;
ALTER TABLE VehiclePart ALTER COLUMN Sku             nvarchar(20)  NOT NULL;
```

**Justification:** The original columns were nullable with widths sized to the sample data only. Marking them `NOT NULL` removes null-check overhead during scans and allows more efficient index storage. Widths were increased to reflect realistic production data — a vehicle name or part name longer than 20 characters is common, and silent truncation at the parameter boundary would cause incorrect query results without any error.

---

### 3. Non-clustered index on `Vehicle.VehicleName`

```sql
CREATE NONCLUSTERED INDEX IX_Vehicle_VehicleName ON Vehicle (VehicleName);
```

**Justification:** `@vehicleName` is the only mandatory parameter and the first condition evaluated in every single call. Without an index, every execution does a full clustered index scan on `Vehicle`. On a large dataset this is the highest-impact index to add — it converts the most selective, always-present filter from a scan to a seek.

---

### 4. Non-clustered index on `VehiclePart.Sku`

```sql
CREATE NONCLUSTERED INDEX IX_VehiclePart_Sku ON VehiclePart (Sku);
```

**Justification:** `@sku` is an optional equality filter. When supplied, it is highly selective on a large parts dataset. Without an index the engine must scan all rows for the matched vehicle before filtering on SKU. The index enables a seek when `@sku` is provided and is skipped cheaply when it is not.

---

### 5. Foreign key with CASCADE DELETE

```sql
ALTER TABLE VehiclePart
ADD CONSTRAINT FK_VehiclePart_Vehicle
    FOREIGN KEY (VehicleID) REFERENCES Vehicle (VehicleID)
    ON DELETE CASCADE;
```

**Justification:** The original schema had no FK enforcing the `VehiclePart.VehicleID` → `Vehicle.VehicleID` relationship. Without it, orphaned parts referencing a deleted vehicle can accumulate silently and corrupt query results. `ON DELETE CASCADE` ensures parts are cleaned up automatically when their parent vehicle is deleted, removing the need for application-level cleanup logic.

---

## Stored Procedure Changes (`usp_VehiclePart_ReadSearch.sql`)

### 6. Parameter widths widened to match column definitions

```sql
-- BEFORE
@vehicleName     nvarchar(20),
@vehiclePartName nvarchar(20) = NULL,
@sku             nvarchar(10) = NULL,

-- AFTER
@vehicleName     nvarchar(50),
@vehiclePartName nvarchar(100) = NULL,
@sku             nvarchar(20)  = NULL,
```

**Justification:** After widening the underlying columns (change #2 above), the procedure parameters must match. When a parameter is narrower than its column, SQL Server silently truncates the passed value before evaluating the `WHERE` clause — a 30-character vehicle name truncated to 20 characters will return no results or wrong results with no error. Parameter widths must always stay in sync with their target column definitions.

---

### 7. `SET NOCOUNT ON` and explicit `BEGIN/END` block

```sql
-- BEFORE
AS
    SELECT ...

-- AFTER
AS
BEGIN
    SET NOCOUNT ON;
    SELECT ...
END;
```

**Justification:** `SET NOCOUNT ON` suppresses the `n rows affected` message after every statement, reducing unnecessary network traffic on a frequently called procedure. The explicit `BEGIN/END` block makes the procedure boundary unambiguous and prevents subtle bugs if additional statements are added later.

---

### 8. `WHERE` clause condition order revised

```sql
-- BEFORE
(vp.VehiclePartName LIKE '%' + @vehiclePartName + '%' OR @vehiclePartName IS NULL)

-- AFTER
(@vehiclePartName IS NULL OR vp.VehiclePartName LIKE '%' + @vehiclePartName + '%')
```

**Justification:** Moving the `IS NULL` check to the left of each `OR` allows SQL Server to short-circuit the column comparison when the parameter is not supplied. In the original form the column expression is always evaluated before the null check. This is a consistent gain on every call where optional parameters are omitted, which is the common case.

---

### 9. `OPTION (RECOMPILE)` added

```sql
OPTION (RECOMPILE);
```

**Justification:** This procedure has multiple optional nullable parameters, meaning the effective query shape changes significantly depending on which are supplied. SQL Server's default plan caching (parameter sniffing) produces a single cached plan that may be optimal for one combination but severely suboptimal for others. `OPTION (RECOMPILE)` forces a fresh plan on each call using the actual runtime values. The recompile overhead is acceptable given the plan quality gain — especially important when `@vehiclePartName` is null (full join across all parts) vs. supplied (narrow filtered join).

---
