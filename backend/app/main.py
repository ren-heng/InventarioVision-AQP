import os
import io
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import openpyxl
from openpyxl.styles import Font, PatternFill

from app.dao.inventario_dao import InventarioDAO
from app.services.vision_service import VisionRecognitionService
from app.services.external_sources_service import ExternalDataAggregatorService

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TEMPLATE_DIR = os.path.join(BASE_DIR, "frontend", "templates")
STATIC_DIR = os.path.join(BASE_DIR, "frontend", "static")
UPLOAD_DIR = os.path.join(STATIC_DIR, "uploads")
DB_PATH = os.path.join(BASE_DIR, "database", "inventariovision_aqp.db")

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR
os.makedirs(UPLOAD_DIR, exist_ok=True)

dao = InventarioDAO(DB_PATH)
vision_service = VisionRecognitionService(UPLOAD_DIR)
external_service = ExternalDataAggregatorService()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/dashboard", methods=["GET"])
def obtener_dashboard():
    productos = dao.listar_productos()
    alertas = dao.listar_alertas()
    escaneos = dao.listar_escaneos()

    valor_total = round(sum(p["valor_inventario"] for p in productos), 2)
    unidades_totales = sum(p["stock_registrado"] for p in productos)
    alertas_pendientes = sum(1 for a in alertas if a["estado"] == "PENDIENTE")

    return jsonify({
        "kpis": {
            "total_productos": len(productos),
            "unidades_totales": unidades_totales,
            "valor_inventario_pen": valor_total,
            "alertas_pendientes": alertas_pendientes,
        },
        "productos": productos,
        "alertas": alertas,
        "escaneos": escaneos,
    })

@app.route("/api/productos", methods=["POST"])
def registrar_producto():
    data = request.get_json()
    nuevo_id = dao.crear_producto(data)
    return jsonify({"mensaje": "Producto registrado exitosamente", "id_producto": nuevo_id}), 201

@app.route("/api/escanear", methods=["POST"])
def escanear_producto():
    id_producto = int(request.form.get("id_producto"))
    producto = dao.obtener_producto(id_producto)
    if not producto:
        return jsonify({"error": "Producto no encontrado"}), 404

    if "imagen" not in request.files:
        return jsonify({"error": "Debe adjuntar una imagen del estante o producto"}), 400

    archivo = request.files["imagen"]
    filename = secure_filename(archivo.filename)
    ruta_guardado = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    archivo.save(ruta_guardado)

    # 1. Procesamiento de Visión Artificial
    resultado_ia = vision_service.analizar_imagen_inventario(
        ruta_guardado, producto["etiqueta_modelo_ia"]
    )

    # 2. Auditoría automática y generación de alertas
    auditoria = dao.registrar_escaneo_y_auditar(
        id_producto=id_producto,
        imagen_nombre=resultado_ia["imagen_procesada"],
        cantidad_detectada=resultado_ia["cantidad_detectada"],
        confianza=resultado_ia["confianza_ia"],
    )

    return jsonify({
        "vision": resultado_ia,
        "auditoria": auditoria,
        "imagen_url": f"/static/uploads/{resultado_ia['imagen_procesada']}",
    })

@app.route("/api/sincronizar-fuentes", methods=["POST"])
def sincronizar_fuentes():
    resultado = external_service.sincronizar_fuentes_oficiales()
    actualizados = dao.actualizar_precios_oficiales(resultado["precios_oficiales"])
    resultado["productos_actualizados_bd"] = actualizados
    return jsonify(resultado)

@app.route("/api/reportes/excel", methods=["GET"])
def exportar_reporte_excel():
    productos = dao.listar_productos()
    alertas = dao.listar_alertas()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Inventario y Precios Oficiales"

    headers = [
        "SKU", "Producto", "Categoría", "Stock Sistema", "Stock Mínimo",
        "Precio Tienda (S/)", "Precio Ref. Oficial (S/)", "Fuente Oficial", "Valor Total (S/)"
    ]
    ws.append(headers)

    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill

    for p in productos:
        ws.append([
            p["sku"], p["nombre"], p["categoria_nombre"], p["stock_registrado"],
            p["stock_minimo"], p["precio_unitario"], p["precio_referencia_oficial"],
            p["fuente_oficial"], p["valor_inventario"]
        ])

    ws_alertas = wb.create_sheet("Alertas e Inconsistencias")
    ws_alertas.append(["ID Alerta", "SKU", "Producto", "Tipo", "Severidad", "Mensaje", "Fecha"])
    for a in alertas:
        ws_alertas.append([
            a["id_alerta"], a["sku"], a["producto_nombre"], a["tipo_alerta"],
            a["severidad"], a["mensaje"], a["fecha_generacion"]
        ])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name="Reporte_Auditoria_InventarioVision_AQP.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

@app.route("/api/productos/<int:id_producto>", methods=["DELETE"])
def eliminar_producto(id_producto):
    eliminado = dao.eliminar_producto(id_producto)
    if not eliminado:
        return jsonify({"error": "Producto no encontrado"}), 404
    return jsonify({"mensaje": "Producto eliminado correctamente"}), 200

@app.route("/api/alertas/<int:id_alerta>/resolver", methods=["POST"])
def resolver_alerta(id_alerta):
    if not dao.resolver_alerta(id_alerta):
        return jsonify({"error": "Alerta no encontrada"}), 404
    return jsonify({"mensaje": "Alerta resuelta"}), 200

if __name__ == "__main__":
    app.run(debug=True, port=5000)

