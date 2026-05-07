/*
    Form Fruta Comercial - Azure SQL DW ETL (Phase 1 Hardening)
    ------------------------------------------------------------
    Script incremental para endurecer staging y agregar auditoria ETL.

    Cambios principales:
    - metadata de lote en stg.FormularioHeader / stg.FormularioDefecto
    - esquema etl con BatchControl, tablas de rechazo y excepciones
    - procedimiento etl.sp_start_formulario_batch
    - reemplazo de dbo.sp_process_formulario_stage con validaciones y rechazos
*/

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'etl')
BEGIN
    EXEC('CREATE SCHEMA etl');
END
GO

-- ============================================================================
-- ETL CONTROL TABLES
-- ============================================================================

IF OBJECT_ID('etl.BatchControl', 'U') IS NULL
BEGIN
    CREATE TABLE etl.BatchControl (
        batch_id                UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        source_run_id           NVARCHAR(100)    NULL,
        source_system           NVARCHAR(50)     NULL,
        status                  NVARCHAR(40)     NOT NULL
            CONSTRAINT DF_etl_BatchControl_status DEFAULT 'RECEIVED',
        header_received_count   INT              NOT NULL
            CONSTRAINT DF_etl_BatchControl_header_received DEFAULT 0,
        header_loaded_count     INT              NOT NULL
            CONSTRAINT DF_etl_BatchControl_header_loaded DEFAULT 0,
        header_rejected_count   INT              NOT NULL
            CONSTRAINT DF_etl_BatchControl_header_rejected DEFAULT 0,
        defect_received_count   INT              NOT NULL
            CONSTRAINT DF_etl_BatchControl_defect_received DEFAULT 0,
        defect_loaded_count     INT              NOT NULL
            CONSTRAINT DF_etl_BatchControl_defect_loaded DEFAULT 0,
        defect_rejected_count   INT              NOT NULL
            CONSTRAINT DF_etl_BatchControl_defect_rejected DEFAULT 0,
        notes                   NVARCHAR(1000)   NULL,
        started_at              DATETIME2(0)     NOT NULL
            CONSTRAINT DF_etl_BatchControl_started_at DEFAULT SYSUTCDATETIME(),
        last_updated_at         DATETIME2(0)     NOT NULL
            CONSTRAINT DF_etl_BatchControl_last_updated DEFAULT SYSUTCDATETIME(),
        completed_at            DATETIME2(0)     NULL
    );
END
GO

IF OBJECT_ID('etl.FormularioExcepcion', 'U') IS NULL
BEGIN
    CREATE TABLE etl.FormularioExcepcion (
        source_system           NVARCHAR(50)    NOT NULL,
        source_business_key     NVARCHAR(100)   NOT NULL,
        reason                  NVARCHAR(500)   NOT NULL,
        is_active               BIT             NOT NULL
            CONSTRAINT DF_etl_FormularioExcepcion_is_active DEFAULT 1,
        created_at              DATETIME2(0)    NOT NULL
            CONSTRAINT DF_etl_FormularioExcepcion_created_at DEFAULT SYSUTCDATETIME(),
        updated_at              DATETIME2(0)    NOT NULL
            CONSTRAINT DF_etl_FormularioExcepcion_updated_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_etl_FormularioExcepcion PRIMARY KEY (source_system, source_business_key)
    );
END
GO

IF OBJECT_ID('etl.RechazoFormularioHeader', 'U') IS NULL
BEGIN
    CREATE TABLE etl.RechazoFormularioHeader (
        rejection_id            BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        batch_id                UNIQUEIDENTIFIER     NULL,
        source_run_id           NVARCHAR(100)        NULL,
        source_system           NVARCHAR(50)         NOT NULL,
        source_business_key     NVARCHAR(100)        NOT NULL,
        source_record_id        BIGINT               NULL,
        row_hash                VARBINARY(32)        NULL,
        reject_reason           NVARCHAR(1000)       NOT NULL,
        fecha                   DATE                 NULL,
        fecha_operacional       DATE                 NULL,
        centro_codigo           NVARCHAR(20)         NULL,
        linea_codigo            NVARCHAR(50)         NULL,
        turno_codigo            VARCHAR(10)          NULL,
        estado_formulario       NVARCHAR(20)         NULL,
        es_completo             BIT                  NULL,
        cant_muestra            INT                  NULL,
        suma_defectos           INT                  NULL,
        fruta_comercial         INT                  NULL,
        fruta_sana              INT                  NULL,
        choice                  INT                  NULL,
        rejected_at             DATETIME2(0)         NOT NULL
            CONSTRAINT DF_etl_RechazoFormularioHeader_rejected_at DEFAULT SYSUTCDATETIME(),
        resolved_at             DATETIME2(0)         NULL
    );
END
GO

IF OBJECT_ID('etl.RechazoFormularioDefecto', 'U') IS NULL
BEGIN
    CREATE TABLE etl.RechazoFormularioDefecto (
        rejection_id            BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        batch_id                UNIQUEIDENTIFIER     NULL,
        source_run_id           NVARCHAR(100)        NULL,
        source_system           NVARCHAR(50)         NOT NULL,
        source_business_key     NVARCHAR(100)        NOT NULL,
        codigo_defecto          NVARCHAR(20)         NOT NULL,
        row_hash                VARBINARY(32)        NULL,
        reject_reason           NVARCHAR(1000)       NOT NULL,
        cantidad                INT                  NULL,
        rejected_at             DATETIME2(0)         NOT NULL
            CONSTRAINT DF_etl_RechazoFormularioDefecto_rejected_at DEFAULT SYSUTCDATETIME(),
        resolved_at             DATETIME2(0)         NULL
    );
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('etl.RechazoFormularioHeader')
      AND name = 'IX_etl_RechazoFormularioHeader_open'
)
BEGIN
    CREATE INDEX IX_etl_RechazoFormularioHeader_open
        ON etl.RechazoFormularioHeader (source_system, source_business_key, resolved_at);
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('etl.RechazoFormularioDefecto')
      AND name = 'IX_etl_RechazoFormularioDefecto_open'
)
BEGIN
    CREATE INDEX IX_etl_RechazoFormularioDefecto_open
        ON etl.RechazoFormularioDefecto (source_system, source_business_key, codigo_defecto, resolved_at);
END
GO

-- ============================================================================
-- STAGING HARDENING
-- ============================================================================

IF COL_LENGTH('stg.FormularioHeader', 'batch_id') IS NULL
BEGIN
    ALTER TABLE stg.FormularioHeader
        ADD batch_id UNIQUEIDENTIFIER NULL;
END
GO

IF COL_LENGTH('stg.FormularioHeader', 'source_run_id') IS NULL
BEGIN
    ALTER TABLE stg.FormularioHeader
        ADD source_run_id NVARCHAR(100) NULL;
END
GO

IF COL_LENGTH('stg.FormularioHeader', 'row_hash') IS NULL
BEGIN
    ALTER TABLE stg.FormularioHeader
        ADD row_hash VARBINARY(32) NULL;
END
GO

IF COL_LENGTH('stg.FormularioHeader', 'ingested_at') IS NULL
BEGIN
    ALTER TABLE stg.FormularioHeader
        ADD ingested_at DATETIME2(0) NULL;
END
GO

IF COL_LENGTH('stg.FormularioHeader', 'rejected_at') IS NULL
BEGIN
    ALTER TABLE stg.FormularioHeader
        ADD rejected_at DATETIME2(0) NULL;
END
GO

IF COL_LENGTH('stg.FormularioHeader', 'reject_reason') IS NULL
BEGIN
    ALTER TABLE stg.FormularioHeader
        ADD reject_reason NVARCHAR(1000) NULL;
END
GO

IF COL_LENGTH('stg.FormularioDefecto', 'batch_id') IS NULL
BEGIN
    ALTER TABLE stg.FormularioDefecto
        ADD batch_id UNIQUEIDENTIFIER NULL;
END
GO

IF COL_LENGTH('stg.FormularioDefecto', 'source_run_id') IS NULL
BEGIN
    ALTER TABLE stg.FormularioDefecto
        ADD source_run_id NVARCHAR(100) NULL;
END
GO

IF COL_LENGTH('stg.FormularioDefecto', 'row_hash') IS NULL
BEGIN
    ALTER TABLE stg.FormularioDefecto
        ADD row_hash VARBINARY(32) NULL;
END
GO

IF COL_LENGTH('stg.FormularioDefecto', 'ingested_at') IS NULL
BEGIN
    ALTER TABLE stg.FormularioDefecto
        ADD ingested_at DATETIME2(0) NULL;
END
GO

IF COL_LENGTH('stg.FormularioDefecto', 'rejected_at') IS NULL
BEGIN
    ALTER TABLE stg.FormularioDefecto
        ADD rejected_at DATETIME2(0) NULL;
END
GO

IF COL_LENGTH('stg.FormularioDefecto', 'reject_reason') IS NULL
BEGIN
    ALTER TABLE stg.FormularioDefecto
        ADD reject_reason NVARCHAR(1000) NULL;
END
GO

UPDATE stg.FormularioHeader
SET ingested_at = COALESCE(ingested_at, created_at, updated_at, SYSUTCDATETIME())
WHERE ingested_at IS NULL;
GO

UPDATE stg.FormularioDefecto
SET ingested_at = COALESCE(ingested_at, updated_at, SYSUTCDATETIME())
WHERE ingested_at IS NULL;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.default_constraints
    WHERE parent_object_id = OBJECT_ID('stg.FormularioHeader')
      AND name = 'DF_stg_FormularioHeader_ingested_at'
)
BEGIN
    ALTER TABLE stg.FormularioHeader
        ADD CONSTRAINT DF_stg_FormularioHeader_ingested_at
        DEFAULT SYSUTCDATETIME() FOR ingested_at;
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.default_constraints
    WHERE parent_object_id = OBJECT_ID('stg.FormularioDefecto')
      AND name = 'DF_stg_FormularioDefecto_ingested_at'
)
BEGIN
    ALTER TABLE stg.FormularioDefecto
        ADD CONSTRAINT DF_stg_FormularioDefecto_ingested_at
        DEFAULT SYSUTCDATETIME() FOR ingested_at;
END
GO

ALTER TABLE stg.FormularioHeader
ALTER COLUMN ingested_at DATETIME2(0) NOT NULL;
GO

ALTER TABLE stg.FormularioDefecto
ALTER COLUMN ingested_at DATETIME2(0) NOT NULL;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('stg.FormularioHeader')
      AND name = 'IX_stg_FormularioHeader_pending'
)
BEGIN
    CREATE INDEX IX_stg_FormularioHeader_pending
        ON stg.FormularioHeader (dw_loaded_at, rejected_at, es_completo);
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('stg.FormularioHeader')
      AND name = 'IX_stg_FormularioHeader_batch'
)
BEGIN
    CREATE INDEX IX_stg_FormularioHeader_batch
        ON stg.FormularioHeader (batch_id, source_run_id, updated_at);
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('stg.FormularioDefecto')
      AND name = 'IX_stg_FormularioDefecto_pending'
)
BEGIN
    CREATE INDEX IX_stg_FormularioDefecto_pending
        ON stg.FormularioDefecto (dw_loaded_at, rejected_at);
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE object_id = OBJECT_ID('stg.FormularioDefecto')
      AND name = 'IX_stg_FormularioDefecto_batch'
)
BEGIN
    CREATE INDEX IX_stg_FormularioDefecto_batch
        ON stg.FormularioDefecto (batch_id, source_run_id, updated_at);
END
GO

-- ============================================================================
-- ETL HELPERS
-- ============================================================================

CREATE OR ALTER PROCEDURE etl.sp_start_formulario_batch
    @source_run_id NVARCHAR(100) = NULL,
    @source_system NVARCHAR(50) = NULL,
    @notes NVARCHAR(1000) = NULL,
    @batch_id UNIQUEIDENTIFIER OUTPUT
AS
BEGIN
    SET NOCOUNT ON;

    SET @batch_id = NEWID();

    INSERT INTO etl.BatchControl (
        batch_id,
        source_run_id,
        source_system,
        status,
        notes
    )
    VALUES (
        @batch_id,
        @source_run_id,
        @source_system,
        'RECEIVED',
        @notes
    );

    SELECT @batch_id AS batch_id;
END
GO

-- ============================================================================
-- ETL PROCESS PROCEDURE (HARDENED)
-- ============================================================================

CREATE OR ALTER PROCEDURE dbo.sp_process_formulario_stage
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @now DATETIME2(0) = SYSUTCDATETIME();

    UPDATE h
    SET row_hash = HASHBYTES(
        'SHA2_256',
        CONCAT(
            COALESCE(h.source_system, ''), '|',
            COALESCE(h.source_business_key, ''), '|',
            COALESCE(CONVERT(NVARCHAR(30), h.fecha, 23), ''), '|',
            COALESCE(CONVERT(NVARCHAR(30), h.fecha_operacional, 23), ''), '|',
            COALESCE(h.turno_codigo, ''), '|',
            COALESCE(h.linea_codigo, ''), '|',
            COALESCE(h.especie, ''), '|',
            COALESCE(h.variedad, ''), '|',
            COALESCE(h.lote, ''), '|',
            COALESCE(CONVERT(NVARCHAR(30), h.cant_muestra), ''), '|',
            COALESCE(CONVERT(NVARCHAR(30), h.suma_defectos), ''), '|',
            COALESCE(CONVERT(NVARCHAR(30), h.fruta_comercial), ''), '|',
            COALESCE(CONVERT(NVARCHAR(30), h.fruta_sana), ''), '|',
            COALESCE(CONVERT(NVARCHAR(30), h.choice), ''), '|',
            COALESCE(CONVERT(NVARCHAR(30), h.updated_at, 126), '')
        )
    )
    FROM stg.FormularioHeader h
    WHERE h.dw_loaded_at IS NULL
      AND h.row_hash IS NULL;

    UPDATE d
    SET row_hash = HASHBYTES(
        'SHA2_256',
        CONCAT(
            COALESCE(d.source_system, ''), '|',
            COALESCE(d.source_business_key, ''), '|',
            COALESCE(d.codigo_defecto, ''), '|',
            COALESCE(CONVERT(NVARCHAR(30), d.cantidad), ''), '|',
            COALESCE(CONVERT(NVARCHAR(30), d.updated_at, 126), '')
        )
    )
    FROM stg.FormularioDefecto d
    WHERE d.dw_loaded_at IS NULL
      AND d.row_hash IS NULL;

    DECLARE @header_reject TABLE (
        source_system       NVARCHAR(50)   NOT NULL,
        source_business_key NVARCHAR(100)  NOT NULL,
        reject_reason       NVARCHAR(1000) NOT NULL
    );

    INSERT INTO @header_reject (
        source_system,
        source_business_key,
        reject_reason
    )
    SELECT
        h.source_system,
        h.source_business_key,
        CASE
            WHEN ex.source_business_key IS NOT NULL
                THEN CONCAT('EXCEPTION_ACTIVA: ', ex.reason)
            WHEN h.cant_muestra <= 0
                THEN 'cant_muestra <= 0'
            WHEN h.suma_defectos < 0
                THEN 'suma_defectos < 0'
            WHEN h.fruta_comercial <> h.suma_defectos
                THEN 'fruta_comercial != suma_defectos'
            WHEN h.fruta_sana < 0
                THEN 'fruta_sana < 0'
            WHEN h.choice < 0
                THEN 'choice < 0'
            WHEN h.fruta_sana + h.choice + h.suma_defectos <> h.cant_muestra
                THEN 'fruta_sana + choice + suma_defectos != cant_muestra'
            WHEN NULLIF(LTRIM(RTRIM(h.centro_codigo)), '') IS NULL
                THEN 'centro_codigo nulo o vacio'
        END AS reject_reason
    FROM stg.FormularioHeader h
    LEFT JOIN etl.FormularioExcepcion ex
        ON ex.is_active = 1
       AND ex.source_system = h.source_system
       AND ex.source_business_key = h.source_business_key
    WHERE h.dw_loaded_at IS NULL
      AND h.rejected_at IS NULL
      AND (
            ex.source_business_key IS NOT NULL
         OR h.cant_muestra <= 0
         OR h.suma_defectos < 0
         OR h.fruta_comercial <> h.suma_defectos
         OR h.fruta_sana < 0
         OR h.choice < 0
         OR h.fruta_sana + h.choice + h.suma_defectos <> h.cant_muestra
         OR NULLIF(LTRIM(RTRIM(h.centro_codigo)), '') IS NULL
      );

    INSERT INTO etl.RechazoFormularioHeader (
        batch_id,
        source_run_id,
        source_system,
        source_business_key,
        source_record_id,
        row_hash,
        reject_reason,
        fecha,
        fecha_operacional,
        centro_codigo,
        linea_codigo,
        turno_codigo,
        estado_formulario,
        es_completo,
        cant_muestra,
        suma_defectos,
        fruta_comercial,
        fruta_sana,
        choice,
        rejected_at
    )
    SELECT
        h.batch_id,
        h.source_run_id,
        h.source_system,
        h.source_business_key,
        h.source_record_id,
        h.row_hash,
        r.reject_reason,
        h.fecha,
        h.fecha_operacional,
        h.centro_codigo,
        h.linea_codigo,
        h.turno_codigo,
        h.estado_formulario,
        h.es_completo,
        h.cant_muestra,
        h.suma_defectos,
        h.fruta_comercial,
        h.fruta_sana,
        h.choice,
        @now
    FROM @header_reject r
    INNER JOIN stg.FormularioHeader h
        ON h.source_system = r.source_system
       AND h.source_business_key = r.source_business_key
    WHERE NOT EXISTS (
        SELECT 1
        FROM etl.RechazoFormularioHeader x
        WHERE x.source_system = h.source_system
          AND x.source_business_key = h.source_business_key
          AND x.reject_reason = r.reject_reason
          AND x.resolved_at IS NULL
    );

    UPDATE h
    SET rejected_at = @now,
        reject_reason = r.reject_reason
    FROM stg.FormularioHeader h
    INNER JOIN @header_reject r
        ON r.source_system = h.source_system
       AND r.source_business_key = h.source_business_key
    WHERE h.dw_loaded_at IS NULL
      AND h.rejected_at IS NULL;

    DECLARE @defect_reject TABLE (
        source_system       NVARCHAR(50)   NOT NULL,
        source_business_key NVARCHAR(100)  NOT NULL,
        codigo_defecto      NVARCHAR(20)   NOT NULL,
        reject_reason       NVARCHAR(1000) NOT NULL
    );

    INSERT INTO @defect_reject (
        source_system,
        source_business_key,
        codigo_defecto,
        reject_reason
    )
    SELECT
        d.source_system,
        d.source_business_key,
        d.codigo_defecto,
        CASE
            WHEN ex.source_business_key IS NOT NULL
                THEN CONCAT('EXCEPTION_ACTIVA: ', ex.reason)
            WHEN h.source_business_key IS NULL
                THEN 'sin header en staging'
            WHEN h.rejected_at IS NOT NULL
                THEN CONCAT('header rechazado: ', COALESCE(h.reject_reason, 'sin detalle'))
            WHEN NULLIF(LTRIM(RTRIM(d.codigo_defecto)), '') IS NULL
                THEN 'codigo_defecto nulo o vacio'
            WHEN d.cantidad < 0
                THEN 'cantidad < 0'
        END AS reject_reason
    FROM stg.FormularioDefecto d
    LEFT JOIN stg.FormularioHeader h
        ON h.source_system = d.source_system
       AND h.source_business_key = d.source_business_key
    LEFT JOIN etl.FormularioExcepcion ex
        ON ex.is_active = 1
       AND ex.source_system = d.source_system
       AND ex.source_business_key = d.source_business_key
    WHERE d.dw_loaded_at IS NULL
      AND d.rejected_at IS NULL
      AND (
            ex.source_business_key IS NOT NULL
         OR h.source_business_key IS NULL
         OR h.rejected_at IS NOT NULL
         OR NULLIF(LTRIM(RTRIM(d.codigo_defecto)), '') IS NULL
         OR d.cantidad < 0
      );

    INSERT INTO etl.RechazoFormularioDefecto (
        batch_id,
        source_run_id,
        source_system,
        source_business_key,
        codigo_defecto,
        row_hash,
        reject_reason,
        cantidad,
        rejected_at
    )
    SELECT
        d.batch_id,
        d.source_run_id,
        d.source_system,
        d.source_business_key,
        d.codigo_defecto,
        d.row_hash,
        r.reject_reason,
        d.cantidad,
        @now
    FROM @defect_reject r
    INNER JOIN stg.FormularioDefecto d
        ON d.source_system = r.source_system
       AND d.source_business_key = r.source_business_key
       AND d.codigo_defecto = r.codigo_defecto
    WHERE NOT EXISTS (
        SELECT 1
        FROM etl.RechazoFormularioDefecto x
        WHERE x.source_system = d.source_system
          AND x.source_business_key = d.source_business_key
          AND x.codigo_defecto = d.codigo_defecto
          AND x.reject_reason = r.reject_reason
          AND x.resolved_at IS NULL
    );

    UPDATE d
    SET rejected_at = @now,
        reject_reason = r.reject_reason
    FROM stg.FormularioDefecto d
    INNER JOIN @defect_reject r
        ON r.source_system = d.source_system
       AND r.source_business_key = d.source_business_key
       AND r.codigo_defecto = d.codigo_defecto
    WHERE d.dw_loaded_at IS NULL
      AND d.rejected_at IS NULL;

    -- Actualizar/insertar especies si no existen (evita FK constraint)
    ;WITH header_src AS (
        SELECT DISTINCT especie
        FROM stg.FormularioHeader
        WHERE dw_loaded_at IS NULL
          AND rejected_at IS NULL
          AND NULLIF(LTRIM(RTRIM(especie)), '') IS NOT NULL
    )
    MERGE dbo.Dim_Especies AS tgt
    USING header_src AS src
        ON tgt.Especie = src.especie
    WHEN NOT MATCHED THEN
        INSERT (Especie)
        VALUES (src.especie)
    WHEN MATCHED THEN
        UPDATE SET
            tgt.Especie = src.especie;

    -- Actualizar/insertar variedades
    ;WITH header_src AS (
        SELECT DISTINCT
            h.especie,
            h.variedad
        FROM stg.FormularioHeader h
        WHERE h.dw_loaded_at IS NULL
          AND h.rejected_at IS NULL
          AND NULLIF(LTRIM(RTRIM(h.variedad)), '') IS NOT NULL
    )
    MERGE dbo.Dim_Variedades AS tgt
    USING (
        SELECT
            e.idEspecie,
            src.variedad
        FROM header_src src
        INNER JOIN dbo.Dim_Especies e
            ON e.Especie = src.especie
    ) AS src
        ON tgt.idEspecie = src.idEspecie
       AND tgt.Variedad = src.variedad
    WHEN MATCHED THEN
        UPDATE SET
            tgt.Variedad = src.variedad
    WHEN NOT MATCHED THEN
        INSERT (idEspecie, Variedad)
        VALUES (src.idEspecie, src.variedad);

    -- Actualizar/insertar productores por CodProductor_SAP
    ;WITH header_src AS (
        SELECT DISTINCT
            productor_codigo,
            productor_nombre,
            productor_display
        FROM stg.FormularioHeader
        WHERE dw_loaded_at IS NULL
          AND rejected_at IS NULL
          AND NULLIF(LTRIM(RTRIM(productor_codigo)), '') IS NOT NULL
    )
    MERGE dbo.Dim_Productores AS tgt
    USING header_src AS src
        ON tgt.CodProductor_SAP = src.productor_codigo
    WHEN MATCHED THEN
        UPDATE SET
            tgt.Productor = src.productor_nombre,
            tgt.Productor_Padre = COALESCE(tgt.Productor_Padre, src.productor_display)
    WHEN NOT MATCHED THEN
        INSERT (CodProductor_SAP, Productor, Productor_Padre)
        VALUES (src.productor_codigo, src.productor_nombre, src.productor_display);

    -- Actualizar/insertar lineas (usa idCentroLogistico)
    ;WITH header_src AS (
        SELECT DISTINCT
            h.centro_codigo,
            h.linea_codigo,
            h.linea_nombre,
            h.especie_principal_linea
        FROM stg.FormularioHeader h
        WHERE h.dw_loaded_at IS NULL
          AND h.rejected_at IS NULL
          AND NULLIF(LTRIM(RTRIM(h.centro_codigo)), '') IS NOT NULL
          AND NULLIF(LTRIM(RTRIM(h.linea_codigo)), '') IS NOT NULL
    )
    MERGE dbo.DimLinea AS tgt
    USING (
        SELECT
            c.idCentroLogistico,
            src.linea_codigo,
            src.linea_nombre,
            src.especie_principal_linea
        FROM header_src src
        INNER JOIN dbo.Dim_CentrosLogisticos c
            ON CAST(c.CodCentro_SAP AS NVARCHAR) = src.centro_codigo
               OR c.Centro_Logistico = src.centro_codigo
    ) AS src
        ON tgt.idCentroLogistico = src.idCentroLogistico
       AND tgt.linea_codigo = src.linea_codigo
    WHEN MATCHED THEN
        UPDATE SET
            tgt.linea_nombre = COALESCE(src.linea_nombre, tgt.linea_nombre, src.linea_codigo),
            tgt.especie_principal = COALESCE(src.especie_principal_linea, tgt.especie_principal),
            tgt.updated_at = @now
    WHEN NOT MATCHED THEN
        INSERT (idCentroLogistico, linea_codigo, linea_nombre, especie_principal)
        VALUES (
            src.idCentroLogistico,
            src.linea_codigo,
            COALESCE(src.linea_nombre, src.linea_codigo),
            src.especie_principal_linea
        );

    -- Actualizar/insertar lugares de seleccion
    ;WITH header_src AS (
        SELECT DISTINCT
            lugar_codigo,
            lugar_nombre
        FROM stg.FormularioHeader
        WHERE dw_loaded_at IS NULL
          AND rejected_at IS NULL
          AND NULLIF(LTRIM(RTRIM(lugar_codigo)), '') IS NOT NULL
    )
    MERGE dbo.DimLugarSeleccion AS tgt
    USING header_src AS src
        ON tgt.lugar_codigo = src.lugar_codigo
    WHEN MATCHED THEN
        UPDATE SET
            tgt.lugar_nombre = COALESCE(src.lugar_nombre, tgt.lugar_nombre),
            tgt.updated_at = @now
    WHEN NOT MATCHED THEN
        INSERT (lugar_codigo, lugar_nombre)
        VALUES (src.lugar_codigo, COALESCE(src.lugar_nombre, src.lugar_codigo));

    -- Actualizar/insertar turnos
    ;WITH header_src AS (
        SELECT DISTINCT
            turno_codigo,
            turno_nombre,
            rango_turno
        FROM stg.FormularioHeader
        WHERE dw_loaded_at IS NULL
          AND rejected_at IS NULL
          AND NULLIF(LTRIM(RTRIM(turno_codigo)), '') IS NOT NULL
    )
    MERGE dbo.DimTurno AS tgt
    USING header_src AS src
        ON tgt.turno_codigo = src.turno_codigo
    WHEN MATCHED THEN
        UPDATE SET
            tgt.turno_nombre = src.turno_nombre,
            tgt.rango_turno = src.rango_turno,
            tgt.updated_at = @now
    WHEN NOT MATCHED THEN
        INSERT (turno_codigo, turno_nombre, rango_turno)
        VALUES (src.turno_codigo, src.turno_nombre, src.rango_turno);

    -- Actualizar/insertar defectos
    ;WITH defect_src AS (
        SELECT DISTINCT
            codigo_defecto,
            COALESCE(nombre_defecto, codigo_defecto) AS nombre_defecto
        FROM stg.FormularioDefecto
        WHERE dw_loaded_at IS NULL
          AND rejected_at IS NULL
          AND NULLIF(LTRIM(RTRIM(codigo_defecto)), '') IS NOT NULL
    )
    MERGE dbo.DimDefecto AS tgt
    USING defect_src AS src
        ON tgt.codigo_defecto = src.codigo_defecto
    WHEN MATCHED THEN
        UPDATE SET
            tgt.nombre_defecto = src.nombre_defecto,
            tgt.updated_at = @now
    WHEN NOT MATCHED THEN
        INSERT (codigo_defecto, nombre_defecto)
        VALUES (src.codigo_defecto, src.nombre_defecto);

    -- Insertar/actualizar FactFormulario
    ;WITH fact_src AS (
        SELECT
            h.source_system,
            h.source_business_key,
            h.source_record_id,
            h.fecha,
            h.fecha_operacional,
            t.turno_key,
            c.idCentroLogistico,
            p.idProductor,
            e.idEspecie,
            v.idVariedad,
            l.linea_key,
            ls.lugar_key,
            h.lote,
            h.verificador,
            h.observaciones,
            h.cant_muestra,
            h.suma_defectos,
            h.fruta_comercial,
            h.fruta_sana,
            h.choice,
            h.porc_exportable,
            h.porc_embalable,
            h.porc_choice,
            h.porc_descartable,
            h.porc_export_manual,
            h.velocidad_kgh,
            h.velocidad_manual,
            h.centro_sin_definir,
            h.estado_formulario,
            h.es_completo,
            h.campos_pendientes,
            h.created_at,
            h.updated_at
        FROM stg.FormularioHeader h
        INNER JOIN dbo.DimTurno t
            ON t.turno_codigo = h.turno_codigo
        INNER JOIN dbo.Dim_Especies e
            ON e.Especie = h.especie
        INNER JOIN dbo.Dim_Variedades v
            ON v.idEspecie = e.idEspecie
           AND v.Variedad = h.variedad
        INNER JOIN dbo.DimLinea l
            ON l.idCentroLogistico = (
                SELECT TOP 1 c.idCentroLogistico
                FROM dbo.Dim_CentrosLogisticos c
                WHERE CAST(c.CodCentro_SAP AS NVARCHAR) = h.centro_codigo
                   OR c.Centro_Logistico = h.centro_codigo
            )
           AND l.linea_codigo = h.linea_codigo
        LEFT JOIN dbo.Dim_CentrosLogisticos c
            ON CAST(c.CodCentro_SAP AS NVARCHAR) = h.centro_codigo
               OR c.Centro_Logistico = h.centro_codigo
        LEFT JOIN dbo.Dim_Productores p
            ON p.CodProductor_SAP = h.productor_codigo
        LEFT JOIN dbo.DimLugarSeleccion ls
            ON ls.lugar_codigo = h.lugar_codigo
        WHERE h.dw_loaded_at IS NULL
          AND h.rejected_at IS NULL
          AND h.es_completo = 1
    )
    MERGE dbo.FactFormulario AS tgt
    USING fact_src AS src
        ON tgt.source_system = src.source_system
       AND tgt.source_business_key = src.source_business_key
    WHEN MATCHED THEN
        UPDATE SET
            tgt.source_record_id = src.source_record_id,
            tgt.fecha = src.fecha,
            tgt.fecha_operacional = src.fecha_operacional,
            tgt.turno_key = src.turno_key,
            tgt.idCentroLogistico = src.idCentroLogistico,
            tgt.idProductor = src.idProductor,
            tgt.idEspecie = src.idEspecie,
            tgt.idVariedad = src.idVariedad,
            tgt.linea_key = src.linea_key,
            tgt.lugar_key = src.lugar_key,
            tgt.lote = src.lote,
            tgt.verificador = src.verificador,
            tgt.observaciones = src.observaciones,
            tgt.cant_muestra = src.cant_muestra,
            tgt.suma_defectos = src.suma_defectos,
            tgt.fruta_comercial = src.fruta_comercial,
            tgt.fruta_sana = src.fruta_sana,
            tgt.choice = src.choice,
            tgt.porc_exportable = src.porc_exportable,
            tgt.porc_embalable = src.porc_embalable,
            tgt.porc_choice = src.porc_choice,
            tgt.porc_descartable = src.porc_descartable,
            tgt.porc_export_manual = src.porc_export_manual,
            tgt.velocidad_kgh = src.velocidad_kgh,
            tgt.velocidad_manual = src.velocidad_manual,
            tgt.centro_sin_definir = src.centro_sin_definir,
            tgt.estado_formulario = src.estado_formulario,
            tgt.es_completo = src.es_completo,
            tgt.campos_pendientes = src.campos_pendientes,
            tgt.created_at = src.created_at,
            tgt.updated_at = src.updated_at,
            tgt.dw_updated_at = @now
    WHEN NOT MATCHED THEN
        INSERT (
            source_system, source_business_key, source_record_id,
            fecha, fecha_operacional, turno_key,
            idCentroLogistico, idProductor, idEspecie, idVariedad,
            linea_key, lugar_key, lote, verificador, observaciones,
            cant_muestra, suma_defectos, fruta_comercial, fruta_sana, choice,
            porc_exportable, porc_embalable, porc_choice, porc_descartable,
            porc_export_manual, velocidad_kgh, velocidad_manual,
            centro_sin_definir, estado_formulario, es_completo, campos_pendientes,
            created_at, updated_at
        )
        VALUES (
            src.source_system, src.source_business_key, src.source_record_id,
            src.fecha, src.fecha_operacional, src.turno_key,
            src.idCentroLogistico, src.idProductor, src.idEspecie, src.idVariedad,
            src.linea_key, src.lugar_key, src.lote, src.verificador, src.observaciones,
            src.cant_muestra, src.suma_defectos, src.fruta_comercial, src.fruta_sana, src.choice,
            src.porc_exportable, src.porc_embalable, src.porc_choice, src.porc_descartable,
            src.porc_export_manual, src.velocidad_kgh, src.velocidad_manual,
            src.centro_sin_definir, src.estado_formulario, src.es_completo, src.campos_pendientes,
            src.created_at, src.updated_at
        );

    -- Insertar/actualizar FactFormularioDefecto
    ;WITH defect_src AS (
        SELECT
            f.formulario_key,
            d.defecto_key,
            s.cantidad,
            s.updated_at
        FROM stg.FormularioDefecto s
        INNER JOIN dbo.FactFormulario f
            ON f.source_system = s.source_system
           AND f.source_business_key = s.source_business_key
        INNER JOIN dbo.DimDefecto d
            ON d.codigo_defecto = s.codigo_defecto
        INNER JOIN stg.FormularioHeader h
            ON h.source_system = s.source_system
           AND h.source_business_key = s.source_business_key
        WHERE s.dw_loaded_at IS NULL
          AND s.rejected_at IS NULL
          AND h.dw_loaded_at IS NULL
          AND h.rejected_at IS NULL
          AND h.es_completo = 1
    )
    MERGE dbo.FactFormularioDefecto AS tgt
    USING defect_src AS src
        ON tgt.formulario_key = src.formulario_key
       AND tgt.defecto_key = src.defecto_key
    WHEN MATCHED THEN
        UPDATE SET
            tgt.cantidad = src.cantidad,
            tgt.updated_at = src.updated_at,
            tgt.dw_updated_at = @now
    WHEN NOT MATCHED THEN
        INSERT (formulario_key, defecto_key, cantidad, updated_at)
        VALUES (src.formulario_key, src.defecto_key, src.cantidad, src.updated_at);

    -- Eliminar defectos no presentes en nuevo batch (clean sync)
    ;WITH forms_in_batch AS (
        SELECT DISTINCT
            f.formulario_key
        FROM stg.FormularioHeader h
        INNER JOIN dbo.FactFormulario f
            ON f.source_system = h.source_system
           AND f.source_business_key = h.source_business_key
        WHERE h.dw_loaded_at IS NULL
          AND h.rejected_at IS NULL
          AND h.es_completo = 1
    )
    DELETE tgt
    FROM dbo.FactFormularioDefecto tgt
    INNER JOIN forms_in_batch b
        ON b.formulario_key = tgt.formulario_key
    WHERE NOT EXISTS (
        SELECT 1
        FROM stg.FormularioDefecto s
        INNER JOIN dbo.DimDefecto d
            ON d.codigo_defecto = s.codigo_defecto
        INNER JOIN dbo.FactFormulario f
            ON f.source_system = s.source_system
           AND f.source_business_key = s.source_business_key
        INNER JOIN stg.FormularioHeader h
            ON h.source_system = s.source_system
           AND h.source_business_key = s.source_business_key
        WHERE s.dw_loaded_at IS NULL
          AND s.rejected_at IS NULL
          AND h.dw_loaded_at IS NULL
          AND h.rejected_at IS NULL
          AND h.es_completo = 1
          AND f.formulario_key = tgt.formulario_key
          AND d.defecto_key = tgt.defecto_key
    );

    -- Marcar como procesadas en staging solo las filas completas ya enviadas a DW
    UPDATE stg.FormularioHeader
    SET dw_loaded_at = @now
    WHERE dw_loaded_at IS NULL
      AND rejected_at IS NULL
      AND es_completo = 1;

    UPDATE s
    SET dw_loaded_at = @now
    FROM stg.FormularioDefecto s
    INNER JOIN stg.FormularioHeader h
        ON h.source_system = s.source_system
       AND h.source_business_key = s.source_business_key
    WHERE s.dw_loaded_at IS NULL
      AND s.rejected_at IS NULL
      AND h.dw_loaded_at = @now
      AND h.rejected_at IS NULL
      AND h.es_completo = 1;

    ;WITH touched_batches AS (
        SELECT DISTINCT batch_id
        FROM stg.FormularioHeader
        WHERE batch_id IS NOT NULL
        UNION
        SELECT DISTINCT batch_id
        FROM stg.FormularioDefecto
        WHERE batch_id IS NOT NULL
    ),
    header_stats AS (
        SELECT
            batch_id,
            COUNT(*) AS header_received_count,
            SUM(CASE WHEN dw_loaded_at IS NOT NULL THEN 1 ELSE 0 END) AS header_loaded_count,
            SUM(CASE WHEN rejected_at IS NOT NULL THEN 1 ELSE 0 END) AS header_rejected_count,
            SUM(CASE WHEN dw_loaded_at IS NULL AND rejected_at IS NULL THEN 1 ELSE 0 END) AS header_pending_count
        FROM stg.FormularioHeader
        WHERE batch_id IS NOT NULL
        GROUP BY batch_id
    ),
    defect_stats AS (
        SELECT
            batch_id,
            COUNT(*) AS defect_received_count,
            SUM(CASE WHEN dw_loaded_at IS NOT NULL THEN 1 ELSE 0 END) AS defect_loaded_count,
            SUM(CASE WHEN rejected_at IS NOT NULL THEN 1 ELSE 0 END) AS defect_rejected_count,
            SUM(CASE WHEN dw_loaded_at IS NULL AND rejected_at IS NULL THEN 1 ELSE 0 END) AS defect_pending_count
        FROM stg.FormularioDefecto
        WHERE batch_id IS NOT NULL
        GROUP BY batch_id
    )
    UPDATE bc
    SET
        bc.header_received_count = COALESCE(hs.header_received_count, 0),
        bc.header_loaded_count = COALESCE(hs.header_loaded_count, 0),
        bc.header_rejected_count = COALESCE(hs.header_rejected_count, 0),
        bc.defect_received_count = COALESCE(ds.defect_received_count, 0),
        bc.defect_loaded_count = COALESCE(ds.defect_loaded_count, 0),
        bc.defect_rejected_count = COALESCE(ds.defect_rejected_count, 0),
        bc.status =
            CASE
                WHEN COALESCE(hs.header_pending_count, 0) + COALESCE(ds.defect_pending_count, 0) > 0
                    THEN 'STAGED'
                WHEN COALESCE(hs.header_rejected_count, 0) + COALESCE(ds.defect_rejected_count, 0) > 0
                    THEN 'COMPLETED_WITH_REJECTIONS'
                WHEN COALESCE(hs.header_loaded_count, 0) + COALESCE(ds.defect_loaded_count, 0) > 0
                    THEN 'COMPLETED'
                ELSE bc.status
            END,
        bc.last_updated_at = @now,
        bc.completed_at =
            CASE
                WHEN COALESCE(hs.header_pending_count, 0) + COALESCE(ds.defect_pending_count, 0) = 0
                    THEN COALESCE(bc.completed_at, @now)
                ELSE NULL
            END
    FROM etl.BatchControl bc
    INNER JOIN touched_batches tb
        ON tb.batch_id = bc.batch_id
    LEFT JOIN header_stats hs
        ON hs.batch_id = bc.batch_id
    LEFT JOIN defect_stats ds
        ON ds.batch_id = bc.batch_id;
END
GO
