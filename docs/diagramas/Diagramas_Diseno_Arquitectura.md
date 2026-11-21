# Diagramas de Diseño y Arquitectura - InventarioVision AQP

## 1. Diagrama Entidad-Relación (Mermaid)
```mermaid
erDiagram
    USUARIOS ||--o{ ESCANEOS_INVENTARIO : realiza
    CATEGORIAS ||--o{ PRODUCTOS : clasifica
    PRODUCTOS ||--o{ ESCANEOS_INVENTARIO : auditado_en
    PRODUCTOS ||--o{ ALERTAS : genera

    PRODUCTOS {
        int id_producto PK
        string sku
        string nombre
        int stock_registrado
        int stock_minimo
        decimal precio_unitario
        decimal precio_referencia_oficial
        string fuente_oficial
        string etiqueta_modelo_ia
    }
    ESCANEOS_INVENTARIO {
        int id_escaneo PK
        int id_producto FK
        string imagen_analizada
        int cantidad_detectada_ia
        int cantidad_sistema_previa
        int diferencia
        decimal confianza_ia
        string estado_auditoria
    }
    ALERTAS {
        int id_alerta PK
        int id_producto FK
        string tipo_alerta
        string severidad
        string mensaje
        string estado
    }
    FUENTES_EXTERNAS_LOG {
        int id_log PK
        string entidad_fuente
        string tipo_fuente
        int registros_sincronizados
        string estado_sincronizacion
    }
```

## 2. Diagrama de Clases UML (Backend Python POO)
```mermaid
classDiagram
    class ProductoDTO {
        +int id_producto
        +str sku
        +str nombre
        +int stock_registrado
        +float precio_unitario
        +calcular_valor_inventario() float
        +requiere_reposicion() bool
    }
    class InventarioDAO {
        -str db_path
        +listar_productos() List
        +crear_producto(data) int
        +registrar_escaneo_y_auditar() Dict
        +listar_alertas() List
    }
    class VisionRecognitionService {
        -str upload_folder
        +analizar_imagen_inventario(image_path, etiqueta) Dict
    }
    class ExternalDataAggregatorService {
        +sincronizar_fuentes_oficiales() Dict
    }
    InventarioDAO --> ProductoDTO : gestiona
```
