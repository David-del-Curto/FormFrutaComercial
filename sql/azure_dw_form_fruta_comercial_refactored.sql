/*
    Form Fruta Comercial - Azure SQL DW ETL (Refactored)
    -------------------------------------------------------
    Script vigente para usar dimensiones existentes en dbo + staging en stg.

    Dimensiones EXISTENTES (no se crean):
    - dbo.Dim_CentrosLogisticos (PK: idCentroLogistico)
    - dbo.Dim_Especies (PK: idEspecie)
    - dbo.Dim_Productores (PK: idProductor)
    - dbo.Dim_Variedades (PK: idVariedad, FK: idEspecie)

    Nuevas tablas/Staging:
    - stg.FormularioHeader
    - stg.FormularioDefecto
    - dbo.DimLinea
    - dbo.DimLugarSeleccion
    - dbo.DimTurno
    - dbo.DimDefecto
    - dbo.FactFormulario
    - dbo.FactFormularioDefecto

    Regla operativa vigente:
    - El DW solo procesa formularios completos (es_completo = 1).
    - Los formularios en borrador permanecen en staging con dw_loaded_at = NULL.
*/

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'stg')
BEGIN
    EXEC('CREATE SCHEMA stg');
END
GO

-- ============================================================================
-- STAGING TABLES
-- ============================================================================

IF OBJECT_ID('stg.FormularioHeader', 'U') IS NULL
BEGIN
    CREATE TABLE stg.FormularioHeader (
        source_system           NVARCHAR(50)    NOT NULL,
        source_business_key     NVARCHAR(100)   NOT NULL,
        source_record_id        BIGINT          NULL,
        fecha                   DATE            NOT NULL,
        fecha_operacional       DATE            NOT NULL,
        turno_codigo            VARCHAR(10)     NOT NULL,
        turno_nombre            NVARCHAR(50)    NOT NULL,
        rango_turno             NVARCHAR(50)    NOT NULL,
        linea_codigo            NVARCHAR(50)    NOT NULL,
        linea_nombre            NVARCHAR(120)   NULL,
        especie                 NVARCHAR(120)   NOT NULL,
        especie_principal_linea NVARCHAR(120)   NULL,
        variedad                NVARCHAR(120)   NOT NULL,
        lote                    NVARCHAR(50)    NOT NULL,
        centro_codigo           NVARCHAR(20)    NULL,
        centro_nombre           NVARCHAR(200)   NULL,
        centro_display          NVARCHAR(250)   NULL,
        productor_codigo        NVARCHAR(50)    NULL,
        productor_nombre        NVARCHAR(200)   NULL,
        productor_display       NVARCHAR(250)   NULL,
        lugar_codigo            VARCHAR(10)     NULL,
        lugar_nombre            NVARCHAR(100)   NULL,
        verificador             NVARCHAR(100)   NULL,
        observaciones           NVARCHAR(1000)  NULL,
        cant_muestra            INT             NOT NULL,
        suma_defectos           INT             NOT NULL,
        fruta_comercial         INT             NOT NULL,
        fruta_sana              INT             NOT NULL,
        choice                  INT             NOT NULL,
        porc_exportable         DECIMAL(9,2)    NOT NULL,
        porc_embalable          DECIMAL(9,2)    NOT NULL,
        porc_choice             DECIMAL(9,2)    NOT NULL,
        porc_descartable        DECIMAL(9,2)    NOT NULL,
        porc_export_manual      INT             NULL,
        velocidad_kgh           DECIMAL(18,2)   NULL,
        velocidad_manual        DECIMAL(18,2)   NULL,
        centro_sin_definir      BIT             NOT NULL,
        estado_formulario       NVARCHAR(20)    NOT NULL,
        es_completo             BIT             NOT NULL,
        campos_pendientes       NVARCHAR(500)   NULL,
        created_at              DATETIME2(0)    NULL,
        updated_at              DATETIME2(0)    NOT NULL,
        dw_loaded_at            DATETIME2(0)    NULL,
        CONSTRAINT PK_stg_FormularioHeader PRIMARY KEY (source_system, source_business_key)
    );
END
GO

IF OBJECT_ID('stg.FormularioDefecto', 'U') IS NULL
BEGIN
    CREATE TABLE stg.FormularioDefecto (
        source_system           NVARCHAR(50)    NOT NULL,
        source_business_key     NVARCHAR(100)   NOT NULL,
        codigo_defecto          NVARCHAR(20)    NOT NULL,
        nombre_defecto          NVARCHAR(200)   NULL,
        cantidad                INT             NOT NULL,
        updated_at              DATETIME2(0)    NOT NULL,
        dw_loaded_at            DATETIME2(0)    NULL,
        CONSTRAINT PK_stg_FormularioDefecto PRIMARY KEY (
            source_system,
            source_business_key,
            codigo_defecto
        )
    );
END
GO

-- ============================================================================
-- NEW DBO DIMENSION TABLES (que no existen)
-- ============================================================================

IF OBJECT_ID('dbo.DimLinea', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.DimLinea (
        linea_key               INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        idCentroLogistico       INT               NOT NULL,
        linea_codigo            NVARCHAR(50)      NOT NULL,
        linea_nombre            NVARCHAR(120)     NULL,
        especie_principal       NVARCHAR(120)     NULL,
        created_at              DATETIME2(0)      NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at              DATETIME2(0)      NOT NULL DEFAULT SYSUTCDATETIME()
    );

    CREATE UNIQUE INDEX UX_DimLinea_centro_linea
        ON dbo.DimLinea (idCentroLogistico, linea_codigo);
END
GO

IF OBJECT_ID('dbo.DimLugarSeleccion', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.DimLugarSeleccion (
        lugar_key               INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        lugar_codigo            VARCHAR(10)       NOT NULL,
        lugar_nombre            NVARCHAR(100)     NOT NULL,
        created_at              DATETIME2(0)      NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at              DATETIME2(0)      NOT NULL DEFAULT SYSUTCDATETIME()
    );

    CREATE UNIQUE INDEX UX_DimLugarSeleccion_codigo
        ON dbo.DimLugarSeleccion (lugar_codigo);
END
GO

IF OBJECT_ID('dbo.DimTurno', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.DimTurno (
        turno_key               INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        turno_codigo            VARCHAR(10)       NOT NULL,
        turno_nombre            NVARCHAR(50)      NOT NULL,
        rango_turno             NVARCHAR(50)      NOT NULL,
        created_at              DATETIME2(0)      NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at              DATETIME2(0)      NOT NULL DEFAULT SYSUTCDATETIME()
    );

    CREATE UNIQUE INDEX UX_DimTurno_codigo
        ON dbo.DimTurno (turno_codigo);
END
GO

IF OBJECT_ID('dbo.DimDefecto', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.DimDefecto (
        defecto_key             INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        codigo_defecto          NVARCHAR(20)      NOT NULL,
        nombre_defecto          NVARCHAR(200)     NOT NULL,
        created_at              DATETIME2(0)      NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at              DATETIME2(0)      NOT NULL DEFAULT SYSUTCDATETIME()
    );

    CREATE UNIQUE INDEX UX_DimDefecto_codigo
        ON dbo.DimDefecto (codigo_defecto);
END
GO

-- ============================================================================
-- FACT TABLES
-- ============================================================================

IF OBJECT_ID('dbo.FactFormulario', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.FactFormulario (
        formulario_key          BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        source_system           NVARCHAR(50)         NOT NULL,
        source_business_key     NVARCHAR(100)        NOT NULL,
        source_record_id        BIGINT               NULL,
        fecha                   DATE                 NOT NULL,
        fecha_operacional       DATE                 NOT NULL,
        turno_key               INT                  NOT NULL,
        idCentroLogistico       INT                  NULL,
        idProductor             INT                  NULL,
        idEspecie               INT                  NOT NULL,
        idVariedad              INT                  NOT NULL,
        linea_key               INT                  NOT NULL,
        lugar_key               INT                  NULL,
        lote                    NVARCHAR(50)         NOT NULL,
        verificador             NVARCHAR(100)        NULL,
        observaciones           NVARCHAR(1000)       NULL,
        cant_muestra            INT                  NOT NULL,
        suma_defectos           INT                  NOT NULL,
        fruta_comercial         INT                  NOT NULL,
        fruta_sana              INT                  NOT NULL,
        choice                  INT                  NOT NULL,
        porc_exportable         DECIMAL(9,2)         NOT NULL,
        porc_embalable          DECIMAL(9,2)         NOT NULL,
        porc_choice             DECIMAL(9,2)         NOT NULL,
        porc_descartable        DECIMAL(9,2)         NOT NULL,
        porc_export_manual      INT                  NULL,
        velocidad_kgh           DECIMAL(18,2)        NULL,
        velocidad_manual        DECIMAL(18,2)        NULL,
        centro_sin_definir      BIT                  NOT NULL,
        estado_formulario       NVARCHAR(20)         NOT NULL,
        es_completo             BIT                  NOT NULL,
        campos_pendientes       NVARCHAR(500)        NULL,
        created_at              DATETIME2(0)         NULL,
        updated_at              DATETIME2(0)         NOT NULL,
        dw_inserted_at          DATETIME2(0)         NOT NULL DEFAULT SYSUTCDATETIME(),
        dw_updated_at           DATETIME2(0)         NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_FactFormulario_DimTurno
            FOREIGN KEY (turno_key) REFERENCES dbo.DimTurno(turno_key),
        CONSTRAINT FK_FactFormulario_DimLinea
            FOREIGN KEY (linea_key) REFERENCES dbo.DimLinea(linea_key),
        CONSTRAINT FK_FactFormulario_DimLugarSeleccion
            FOREIGN KEY (lugar_key) REFERENCES dbo.DimLugarSeleccion(lugar_key)
    );

    CREATE UNIQUE INDEX UX_FactFormulario_source_key
        ON dbo.FactFormulario (source_system, source_business_key);
END
GO

IF OBJECT_ID('dbo.FactFormularioDefecto', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.FactFormularioDefecto (
        formulario_key          BIGINT         NOT NULL,
        defecto_key             INT            NOT NULL,
        cantidad                INT            NOT NULL,
        updated_at              DATETIME2(0)   NOT NULL,
        dw_updated_at           DATETIME2(0)   NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_FactFormularioDefecto
            PRIMARY KEY (formulario_key, defecto_key),
        CONSTRAINT FK_FactFormularioDefecto_Formulario
            FOREIGN KEY (formulario_key) REFERENCES dbo.FactFormulario(formulario_key),
        CONSTRAINT FK_FactFormularioDefecto_Defecto
            FOREIGN KEY (defecto_key) REFERENCES dbo.DimDefecto(defecto_key)
    );
END
GO

-- ============================================================================
-- SEED STATIC CATALOGS
-- ============================================================================

CREATE OR ALTER PROCEDURE dbo.sp_seed_static_catalogs
AS
BEGIN
    SET NOCOUNT ON;

    MERGE dbo.DimLugarSeleccion AS tgt
    USING (
        SELECT 'MS' AS lugar_codigo, 'Mesa Seleccion' AS lugar_nombre
        UNION ALL SELECT 'BC', 'Bins Comercial'
        UNION ALL SELECT 'TP', 'Trypack'
    ) AS src
        ON tgt.lugar_codigo = src.lugar_codigo
    WHEN MATCHED THEN
        UPDATE SET
            tgt.lugar_nombre = src.lugar_nombre,
            tgt.updated_at = SYSUTCDATETIME()
    WHEN NOT MATCHED THEN
        INSERT (lugar_codigo, lugar_nombre)
        VALUES (src.lugar_codigo, src.lugar_nombre);

    MERGE dbo.DimTurno AS tgt
    USING (
        SELECT 'T1' AS turno_codigo, 'Turno 1' AS turno_nombre, '07:00-17:00' AS rango_turno
        UNION ALL SELECT 'T2', 'Turno 2', '17:00-02:00'
    ) AS src
        ON tgt.turno_codigo = src.turno_codigo
    WHEN MATCHED THEN
        UPDATE SET
            tgt.turno_nombre = src.turno_nombre,
            tgt.rango_turno = src.rango_turno,
            tgt.updated_at = SYSUTCDATETIME()
    WHEN NOT MATCHED THEN
        INSERT (turno_codigo, turno_nombre, rango_turno)
        VALUES (src.turno_codigo, src.turno_nombre, src.rango_turno);

    MERGE dbo.DimDefecto AS tgt
    USING (
        SELECT 'HAO' AS codigo_defecto, 'Herida Abierta (Oxidada)' AS nombre_defecto
        UNION ALL SELECT 'HAF', 'Herida Abierta (Fresca)'
        UNION ALL SELECT 'MAC', 'Machucon'
        UNION ALL SELECT 'PAR', 'Partidura'
        UNION ALL SELECT 'GSS', 'Golpe Sol Severo'
        UNION ALL SELECT 'CRA', 'Cracking'
        UNION ALL SELECT 'DES', 'Deshidratacion'
        UNION ALL SELECT 'DP', 'Desgarro Pedicelar'
        UNION ALL SELECT 'LEN', 'Lenticelosis'
        UNION ALL SELECT 'BP', 'Bitter Pit'
        UNION ALL SELECT 'MR', 'Manchas - Roce'
        UNION ALL SELECT 'RLP', 'Roce (Linea Proceso)'
        UNION ALL SELECT 'FC', 'Falta Color'
        UNION ALL SELECT 'HC', 'Herida Cicatrizada'
        UNION ALL SELECT 'DI', 'Dano Insecto'
        UNION ALL SELECT 'DEF', 'Deforme'
        UNION ALL SELECT 'RAM', 'Ramaleo'
        UNION ALL SELECT 'RG', 'Roce Grave'
        UNION ALL SELECT 'RUS', 'Russet Grave'
        UNION ALL SELECT 'VEN', 'Venturia'
        UNION ALL SELECT 'PEN', 'Penacho'
        UNION ALL SELECT 'QSOL', 'Quemado de sol'
        UNION ALL SELECT 'INF', 'Infiltracion'
        UNION ALL SELECT 'PARD', 'Pardeamiento'
        UNION ALL SELECT 'COR', 'Corcho'
        UNION ALL SELECT 'EUL', 'Eulia'
        UNION ALL SELECT 'DQU', 'Dano quimico'
    ) AS src
        ON tgt.codigo_defecto = src.codigo_defecto
    WHEN MATCHED THEN
        UPDATE SET
            tgt.nombre_defecto = src.nombre_defecto,
            tgt.updated_at = SYSUTCDATETIME()
    WHEN NOT MATCHED THEN
        INSERT (codigo_defecto, nombre_defecto)
        VALUES (src.codigo_defecto, src.nombre_defecto);
END
GO

-- ============================================================================
-- ETL PROCESS PROCEDURE
-- ============================================================================

CREATE OR ALTER PROCEDURE dbo.sp_process_formulario_stage
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @now DATETIME2(0) = SYSUTCDATETIME();

    -- Actualizar/insertar especies si no existen (evita FK constraint)
    ;WITH header_src AS (
        SELECT DISTINCT especie
        FROM stg.FormularioHeader
        WHERE dw_loaded_at IS NULL
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
          AND h.dw_loaded_at IS NULL
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
          AND h.dw_loaded_at IS NULL
          AND h.es_completo = 1
          AND f.formulario_key = tgt.formulario_key
          AND d.defecto_key = tgt.defecto_key
    );

    -- Marcar como procesadas en staging solo las filas completas ya enviadas a DW
    UPDATE stg.FormularioHeader
    SET dw_loaded_at = @now
    WHERE dw_loaded_at IS NULL
      AND es_completo = 1;

    UPDATE s
    SET dw_loaded_at = @now
    FROM stg.FormularioDefecto s
    INNER JOIN stg.FormularioHeader h
        ON h.source_system = s.source_system
       AND h.source_business_key = s.source_business_key
    WHERE s.dw_loaded_at IS NULL
      AND h.dw_loaded_at = @now
      AND h.es_completo = 1;
END
GO
