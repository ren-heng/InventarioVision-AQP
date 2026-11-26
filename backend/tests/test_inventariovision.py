import os
import tempfile
import cv2
import numpy as np
from app.dao.inventario_dao import InventarioDAO
from app.services.vision_service import VisionRecognitionService
from app.services.external_sources_service import ExternalDataAggregatorService

def test_auditoria_faltante_genera_alerta():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    dao = InventarioDAO(db_path)
    # Producto 1 tiene 45 unidades registradas; simulamos detección de 40
    res = dao.registrar_escaneo_y_auditar(1, "test.jpg", 40, 95.5)
    assert res["estado_auditoria"] == "FALTANTE"
    assert res["diferencia"] == -5
    assert res["alerta_generada"] is True
    os.remove(db_path)

def test_vision_service_detecta_objetos_sinteticos():
    with tempfile.TemporaryDirectory() as tmpdir:
        img_path = os.path.join(tmpdir, "estante.png")
        img = np.ones((400, 600, 3), dtype=np.uint8) * 255
        # Dibujar 3 cajas rectangulares simulando productos en estante
        cv2.rectangle(img, (40, 80), (140, 260), (30, 80, 180), -1)
        cv2.rectangle(img, (200, 80), (300, 260), (30, 150, 60), -1)
        cv2.rectangle(img, (360, 80), (460, 260), (180, 60, 40), -1)
        cv2.imwrite(img_path, img)

        service = VisionRecognitionService(tmpdir, motor="opencv")
        resultado = service.analizar_imagen_inventario(img_path, "bolsa_arroz")
        assert resultado["cantidad_detectada"] == 3
        assert resultado["confianza_ia"] > 0.0
        assert resultado["motor"] == "opencv"

def test_sincronizacion_fuentes_oficiales():
    ext = ExternalDataAggregatorService()
    data = ext.sincronizar_fuentes_oficiales()
    assert data["total_fuentes"] == 3
    assert data["total_registros_recuperados"] > 0
