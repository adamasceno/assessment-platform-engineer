CREATE PROCEDURE dbo.usp_VehiclePart_UpdateDisplayOrder
    @JsonData NVARCHAR(MAX)
AS
BEGIN
    SET NOCOUNT ON;
	
    IF @JsonData IS NULL OR ISJSON(@JsonData) = 0
    BEGIN
        RETURN 1; 
    END

    BEGIN TRY
        BEGIN TRANSACTION;
    
    	SELECT * 
		INTO #NewOrdersTemp
		FROM OPENJSON(@JsonData)
		WITH (VehiclePartID INT '$.VehiclePartID', DisplayOrder INT '$.DisplayOrder')
		
		-- Merge the temp table with VehiclePart and update when necessary 
        MERGE INTO VehiclePart AS Target
        USING #NewOrdersTemp AS Source
        ON Target.VehiclePartID = Source.VehiclePartID
        WHEN MATCHED THEN
            UPDATE SET Target.DisplayOrder = Source.DisplayOrder;

        COMMIT TRANSACTION;
        RETURN 0; -- Return Code: Success
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
        RETURN 2;
    END CATCH
END;