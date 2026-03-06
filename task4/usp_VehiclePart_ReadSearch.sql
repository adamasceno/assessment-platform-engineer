
-- SPROC Changes --

/*
	Search for parts for a certain vehicle

	@param vehicleName Limit to this vehicle
	@param vehiclePartName Limit to this part. Null for all
	@param sku Limit to this SKU. Null for all
	@param isStockItem Limit to stock values. Null for all

	return 0
*/

ALTER PROCEDURE usp_VehiclePart_ReadSearch

    -- Match the widened column definitions
	@vehicleName nvarchar(50),
	@vehiclePartName nvarchar(100) = NULL,
	@sku nvarchar(20) = NULL,
	@isStockItem bit = NULL
AS
BEGIN
    SET NOCOUNT ON;

    SELECT 
        v.VehicleName,
        vp.VehiclePartName,
        vp.Sku, 
        vp.IsStockItem
	FROM 
	Vehicle v 
	JOIN VehiclePart vp ON v.VehicleID = vp.VehicleID
    WHERE 
        v.VehicleName = @vehicleName
        -- Moving those ANDs to the front of the line, just to increase visibility
        AND (@vehiclePartName IS NULL OR vp.VehiclePartName LIKE '%' + @vehiclePartName + '%')
        AND (@sku IS NULL OR vp.Sku = @sku)
        AND (@isStockItem IS NULL OR vp.IsStockItem = @isStockItem)
    -- Added this to generate a new exec plan on each execution, to help with parameter sniffing    
    OPTION (RECOMPILE); 
END;
	