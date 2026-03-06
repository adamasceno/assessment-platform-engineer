-- Tables Changes --

-- Adding PK to both tables
ALTER TABLE Vehicle 
ADD CONSTRAINT PK_Vehicle PRIMARY KEY CLUSTERED (VehicleID);
ALTER TABLE VehiclePart 
ADD CONSTRAINT PK_VehiclePart PRIMARY KEY CLUSTERED (VehiclePartID);

-- Those are important, so, no nulls for them
ALTER TABLE Vehicle ALTER COLUMN VehicleName nvarchar(50) NOT NULL;
ALTER TABLE VehiclePart ALTER COLUMN VehiclePartName nvarchar(100) NOT NULL;
ALTER TABLE VehiclePart ALTER COLUMN Sku nvarchar(20) NOT NULL;

CREATE NONCLUSTERED INDEX IX_Vehicle_VehicleName ON Vehicle (VehicleName);

-- If something would like to use SKU to query something
CREATE NONCLUSTERED INDEX IX_VehiclePart_Sku ON VehiclePart (Sku);

-- Add FK, connecting them
ALTER TABLE VehiclePart
ADD CONSTRAINT FK_VehiclePart_Vehicle FOREIGN KEY (VehicleID) 
    REFERENCES Vehicle (VehicleID)
    ON DELETE CASCADE; -- If the vehicle goes, the parts should also go, i guess.

