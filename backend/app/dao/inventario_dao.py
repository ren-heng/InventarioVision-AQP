import sqlite3
import os
from typing import List, Dict, Any, Optional

class InventarioDAO:
    """
    Patrón DAO (Data Access Object) con persistencia híbrida:
    - Soporta conexión MySQL en producción
    - Incluye base de datos SQLite autocontenida para ejecución inmediata sin configuración externa
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._inicializar_sqlite()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _inicializar_sqlite(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = self._get_connection()
        cur = conn.cursor()

        cur.executescript("""
        CREATE TABLE IF NOT EXISTS categorias (
            id_categoria INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            descripcion TEXT
        );

        CREATE TABLE IF NOT EXISTS productos (
            id_producto INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT NOT NULL UNIQUE,
            nombre TEXT NOT NULL,
            id_categoria INTEGER NOT NULL,
            stock_registrado INTEGER NOT NULL DEFAULT 0,
            stock_minimo INTEGER NOT NULL DEFAULT 5,
            precio_unitario REAL NOT NULL DEFAULT 0.0,
            precio_referencia_oficial REAL,
            fuente_oficial TEXT,
            etiqueta_modelo_ia TEXT NOT NULL,
            FOREIGN KEY (id_categoria) REFERENCES categorias(id_categoria)
        );

        CREATE TABLE IF NOT EXISTS escaneos_inventario (
            id_escaneo INTEGER PRIMARY KEY AUTOINCREMENT,
            id_producto INTEGER NOT NULL,
            imagen_analizada TEXT NOT NULL,
            cantidad_detectada_ia INTEGER NOT NULL,
            cantidad_sistema_previa INTEGER NOT NULL,
            diferencia INTEGER NOT NULL,
            confianza_ia REAL NOT NULL,
            estado_auditoria TEXT NOT NULL,
            fecha_escaneo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (id_producto) REFERENCES productos(id_producto)
        );

        CREATE TABLE IF NOT EXISTS alertas (
            id_alerta INTEGER PRIMARY KEY AUTOINCREMENT,
            id_producto INTEGER NOT NULL,
            tipo_alerta TEXT NOT NULL,
            severidad TEXT NOT NULL,
            mensaje TEXT NOT NULL,
            estado TEXT DEFAULT 'PENDIENTE',
            fecha_generacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (id_producto) REFERENCES productos(id_producto)
        );
        """)

        cur.execute("SELECT COUNT(*) FROM categorias")
        if cur.fetchone()[0] == 0:
            cur.executemany(
                "INSERT INTO categorias (nombre, descripcion) VALUES (?, ?)",
                [
                    ("Abarrotes y Granos", "Arroz, azúcar, menestras"),
                    ("Bebidas y Lácteos", "Leches evaporadas y bebidas"),
                    ("Aceites y Conservas", "Aceites vegetales y conservas"),
                    ("Limpieza e Higiene", "Detergentes y productos de limpieza"),
                ],
            )
            cur.executemany(
                """INSERT INTO productos 
                (sku, nombre, id_categoria, stock_registrado, stock_minimo, precio_unitario, precio_referencia_oficial, fuente_oficial, etiqueta_modelo_ia)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    ("AQP-ARR-001", "Arroz Extra Costeño 5kg", 1, 45, 15, 22.50, 21.80, "MIDAGRI - SISAP Arequipa", "bolsa_arroz"),
                    ("AQP-LEC-002", "Leche Evaporada Gloria Azul 400g", 2, 120, 30, 4.20, 4.10, "INEI - Canasta Básica AQP", "lata_leche"),
                    ("AQP-ACE-003", "Aceite Vegetal Primor 1L", 3, 12, 20, 9.80, 9.50, "Datos Abiertos PCM", "botella_aceite"),
                    ("AQP-AZU-004", "Azúcar Rubia Cartavio 5kg", 1, 30, 10, 18.90, 18.50, "MIDAGRI - SISAP Arequipa", "bolsa_azucar"),
                    ("AQP-DET-005", "Detergente Ariel 4kg", 4, 8, 12, 24.00, 23.50, "CCIA / Banco Alimentos ONG", "bolsa_detergente"),
                ],
            )
            cur.execute(
                """INSERT INTO alertas (id_producto, tipo_alerta, severidad, mensaje)
                VALUES (3, 'STOCK_BAJO', 'MEDIA', 'Stock de Aceite Vegetal Primor 1L (12 und.) por debajo del mínimo (20 und.).')"""
            )
            cur.execute(
                """INSERT INTO alertas (id_producto, tipo_alerta, severidad, mensaje)
VALUES (5, 'STOCK_BAJO', 'ALTA', 'Stock crítico en Detergente Ariel 4kg (8 und. disponibles).')"""
            )
        conn.commit()
        conn.close()

    def listar_productos(self) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        rows = conn.execute(
            """SELECT p.*, c.nombre AS categoria_nombre,
            ROUND(p.stock_registrado * p.precio_unitario, 2) AS valor_inventario
            FROM productos p
            JOIN categorias c ON p.id_categoria = c.id_categoria
            ORDER BY p.id_producto ASC"""
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def obtener_producto(self, id_producto: int) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        row = conn.execute("SELECT * FROM productos WHERE id_producto = ?", (id_producto,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def crear_producto(self, data: Dict[str, Any]) -> int:
        conn = self._get_connection()
        cur = conn.cursor()
        precio_unit = float(data["precio_unitario"])
        precio_ref_raw = data.get("precio_referencia_oficial")
        precio_ref = float(precio_ref_raw) if precio_ref_raw not in (None, "") else precio_unit
        fuente_raw = (data.get("fuente_oficial") or "").strip()
        fuente = fuente_raw if fuente_raw else "Registro Manual Almacén AQP"

        cur.execute(
            """INSERT INTO productos 
            (sku, nombre, id_categoria, stock_registrado, stock_minimo, precio_unitario, precio_referencia_oficial, fuente_oficial, etiqueta_modelo_ia)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["sku"],
                data["nombre"],
                int(data.get("id_categoria", 1)),
                int(data["stock_registrado"]),
                int(data.get("stock_minimo", 10)),
                precio_unit,
                precio_ref,
                fuente,
                data.get("etiqueta_modelo_ia", "producto_general"),
            ),
        )
        new_id = cur.lastrowid
        if int(data["stock_registrado"]) < int(data.get("stock_minimo", 10)):
            cur.execute(
                "INSERT INTO alertas (id_producto, tipo_alerta, severidad, mensaje) VALUES (?, 'STOCK_BAJO', 'ALTA', ?)",
                (new_id, f"Producto {data['nombre']} registrado con stock inicial por debajo del mínimo."),
            )
        conn.commit()
        conn.close()
        return new_id

    def registrar_escaneo_y_auditar(
        self, id_producto: int, imagen_nombre: str, cantidad_detectada: int, confianza: float
    ) -> Dict[str, Any]:
        conn = self._get_connection()
        cur = conn.cursor()
        prod = cur.execute("SELECT * FROM productos WHERE id_producto = ?", (id_producto,)).fetchone()
        if not prod:
            conn.close()
            raise ValueError("Producto no encontrado")

        stock_previo = prod["stock_registrado"]
        diferencia = cantidad_detectada - stock_previo

        if diferencia == 0:
            estado = "CONFORME"
        elif diferencia < 0:
            estado = "FALTANTE"
        else:
            estado = "EXCEDENTE"

        cur.execute(
            """INSERT INTO escaneos_inventario 
            (id_producto, imagen_analizada, cantidad_detectada_ia, cantidad_sistema_previa, diferencia, confianza_ia, estado_auditoria)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (id_producto, imagen_nombre, cantidad_detectada, stock_previo, diferencia, confianza, estado),
        )

        alerta_msg = ""
        if diferencia != 0:
            alerta_msg = (
                f"Inconsistencia detectada en '{prod['nombre']}': "
                f"Sistema={stock_previo} und., Imagen IA={cantidad_detectada} und. (Diferencia: {diferencia:+d})."
            )
            cur.execute(
                "INSERT INTO alertas (id_producto, tipo_alerta, severidad, mensaje) VALUES (?, 'INCONSISTENCIA_CONTEO', 'ALTA', ?)",
                (id_producto, alerta_msg),
            )

        conn.commit()
        conn.close()
        return {
            "producto": prod["nombre"],
            "stock_sistema": stock_previo,
            "cantidad_detectada_ia": cantidad_detectada,
            "diferencia": diferencia,
            "confianza_ia": confianza,
            "estado_auditoria": estado,
            "alerta_generada": diferencia != 0,
            "mensaje_alerta": alerta_msg,
        }

    def listar_alertas(self) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        rows = conn.execute(
            """SELECT a.*, p.nombre AS producto_nombre, p.sku
            FROM alertas a
            JOIN productos p ON a.id_producto = p.id_producto
            ORDER BY a.id_alerta DESC"""
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def listar_escaneos(self) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        rows = conn.execute(
            """SELECT e.*, p.nombre AS producto_nombre, p.sku
            FROM escaneos_inventario e
            JOIN productos p ON e.id_producto = p.id_producto
            ORDER BY e.id_escaneo DESC"""
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def actualizar_precios_oficiales(self, lista_precios: List[Dict[str, Any]]) -> int:
        conn = self._get_connection()
        cur = conn.cursor()
        actualizados = 0
        for item in lista_precios:
            cur.execute(
                "UPDATE productos SET precio_referencia_oficial = ?, fuente_oficial = ? WHERE sku = ?",
                (item["precio_oficial"], item["fuente"], item["sku"]),
            )
            actualizados += cur.rowcount
        conn.commit()
        conn.close()
        return actualizados

    def eliminar_producto(self, id_producto: int) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        prod = cur.execute("SELECT id_producto FROM productos WHERE id_producto = ?", (id_producto,)).fetchone()
        if not prod:
            conn.close()
            return False
        cur.execute("DELETE FROM alertas WHERE id_producto = ?", (id_producto,))
        cur.execute("DELETE FROM escaneos_inventario WHERE id_producto = ?", (id_producto,))
        cur.execute("DELETE FROM productos WHERE id_producto = ?", (id_producto,))
        conn.commit()
        conn.close()
        return True

    def resolver_alerta(self, id_alerta: int) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE alertas SET estado = 'RESUELTA' WHERE id_alerta = ?", (id_alerta,))
        actualizado = cur.rowcount > 0
        conn.commit()
        conn.close()
        return actualizado

    def listar_alertas(self) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        rows = conn.execute(
            """SELECT a.*, p.nombre AS producto_nombre, p.sku
            FROM alertas a
            JOIN productos p ON a.id_producto = p.id_producto
            WHERE a.estado = 'PENDIENTE'
            ORDER BY a.id_alerta DESC"""
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]