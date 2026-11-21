# InventarioVision AQP

Sistema web académico de gestión y auditoría de inventario para almacenes en **Arequipa, Perú**, combinando **visión por computadora (OpenCV)** para conteo de unidades en estantes y **sincronización de precios de referencia** con fuentes externas (Datos Abiertos Perú / MIDAGRI / INEI, Cámara de Comercio e Industria de Arequipa - CCIA y Banco de Alimentos Perú).

## Arquitectura y tecnologías
- **Backend:** Python + Flask (`backend/app/main.py`)
- **Base de datos:** SQLite (`database/inventariovision_aqp.db` y respaldo `database/inventariovision_aqp_backup.sql`)
- **Visión por computadora:** OpenCV (`backend/app/services/vision_service.py`) — detección de contornos/unidades como herramienta de auditoría de stock.
- **Fuentes externas:** Agregador con respaldo local activo (`backend/app/services/external_sources_service.py`).
- **Frontend:** HTML, CSS y JavaScript (`frontend/`)
- **Reportes:** Exportación a Excel con `openpyxl`.

## Funcionalidades principales
- **Dashboard y control de roles:** Vista de Administrador (`ADMIN`) y Almacenero (`ALMACENERO`).
- **Catálogo de productos:** Registro y eliminación de productos, control de stock mínimo, precios unitarios y comparativa con precio de referencia oficial.
- **Escaneo IA de estantes:** Carga de imagen y selección del producto a auditar para contrastar unidades detectadas frente al stock registrado.
- **Centro de alertas:** Generación y resolución de alertas por inconsistencias de conteo o stock bajo.
- **Fuentes oficiales:** Sincronización de precios referenciales con estrategia de respaldo local (`RESPALDO_LOCAL_ACTIVO`) cuando una fuente externa no responde.

## Cómo ejecutar el proyecto
1. Crear y activar un entorno virtual en Python.
2. Instalar dependencias:
   ```bash
   pip install -r backend/requirements.txt
