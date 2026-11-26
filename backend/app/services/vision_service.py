import os
import cv2
import numpy as np
from typing import Dict, Any, List, Tuple, Optional

Caja = Tuple[int, int, int, int]  # x, y, w, h


class VisionRecognitionService:
    """
    Motor de visión para contar productos en estantes.

    Motor principal: YOLO (ultralytics) a alta resolución (imgsz=1280), sin SAHI.
    Respaldo: detección por contornos con OpenCV (si ultralytics no está instalado
    o el modelo no se puede cargar).

    Configuración por variables de entorno (todas opcionales):
      YOLO_MODEL   ruta o nombre de pesos   (por defecto: yolov8s.pt)
      YOLO_CONF    confianza mínima         (por defecto: 0.20)
      YOLO_IOU     umbral IoU del NMS       (por defecto: 0.50)
      YOLO_IMGSZ   resolución de inferencia (por defecto: 1280)
      YOLO_MAX_DET máximo de detecciones    (por defecto: 300)
    """

    def __init__(self, upload_folder: str, motor: str = "auto"):
        """motor: 'auto' (YOLO y, si falla, OpenCV), 'yolo' u 'opencv'."""
        self.upload_folder = upload_folder
        os.makedirs(self.upload_folder, exist_ok=True)
        self.motor_preferido = motor
        self.modelo_nombre = os.environ.get("YOLO_MODEL", "yolov8s.pt")
        self.conf = float(os.environ.get("YOLO_CONF", "0.20"))
        self.iou = float(os.environ.get("YOLO_IOU", "0.50"))
        self.imgsz = int(os.environ.get("YOLO_IMGSZ", "1280"))
        self.max_det = int(os.environ.get("YOLO_MAX_DET", "300"))
        self._modelo = None
        self._yolo_no_disponible = False

    # ------------------------------------------------------------------ YOLO
    def _cargar_yolo(self):
        """Carga perezosa: no retrasa el arranque de Flask ni los tests."""
        if self._modelo is not None:
            return self._modelo
        if self._yolo_no_disponible:
            return None
        try:
            from ultralytics import YOLO
            self._modelo = YOLO(self.modelo_nombre)
        except Exception as exc:  # ImportError, pesos no encontrados, sin internet
            self._yolo_no_disponible = True
            if self.motor_preferido == "yolo":
                raise RuntimeError(f"No se pudo cargar YOLO ({self.modelo_nombre}): {exc}")
            return None
        return self._modelo

    def _detectar_yolo(self, img: np.ndarray) -> Tuple[List[Caja], List[float]]:
        modelo = self._cargar_yolo()
        if modelo is None:
            raise RuntimeError("YOLO no disponible")

        resultados = modelo.predict(
            img,
            imgsz=self.imgsz,
            conf=self.conf,
            iou=self.iou,
            max_det=self.max_det,
            agnostic_nms=True,  # un mismo objeto no se cuenta como 2 clases
            verbose=False,
        )
        r = resultados[0]
        cajas: List[Caja] = []
        scores: List[float] = []
        if r.boxes is None:
            return cajas, scores
        for xyxy, c in zip(r.boxes.xyxy.cpu().numpy(), r.boxes.conf.cpu().numpy()):
            x1, y1, x2, y2 = [int(v) for v in xyxy]
            cajas.append((x1, y1, x2 - x1, y2 - y1))
            scores.append(float(c))
        return self._filtrar_cajas(cajas, scores, img.shape[1] * img.shape[0])

    @staticmethod
    def _filtrar_cajas(
        cajas: List[Caja], scores: List[float], area_total: int
    ) -> Tuple[List[Caja], List[float]]:
        """Descarta cajas absurdas: casi toda la imagen (fondo/estante) o diminutas."""
        out_c: List[Caja] = []
        out_s: List[float] = []
        for (x, y, w, h), s in zip(cajas, scores):
            area = w * h
            if area > 0.60 * area_total and len(cajas) > 1:
                continue
            if area < 0.0003 * area_total or w < 8 or h < 8:
                continue
            out_c.append((x, y, w, h))
            out_s.append(s)
        return out_c, out_s

    # ---------------------------------------------------------------- OpenCV
    @staticmethod
    def _iou(box_a: Caja, box_b: Caja) -> float:
        ax, ay, aw, ah = box_a
        bx, by, bw, bh = box_b
        x1, y1 = max(ax, bx), max(ay, by)
        x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
        if x2 <= x1 or y2 <= y1:
            return 0.0
        inter = (x2 - x1) * (y2 - y1)
        union = (aw * ah) + (bw * bh) - inter
        return inter / float(union) if union > 0 else 0.0

    @staticmethod
    def _es_contenido(inner: Caja, outer: Caja) -> bool:
        ix, iy, iw, ih = inner
        ox, oy, ow, oh = outer
        return ix >= ox - 4 and iy >= oy - 4 and (ix + iw) <= (ox + ow + 4) and (iy + ih) <= (oy + oh + 4)

    def _suprimir_duplicados(self, cajas: List[Caja]) -> List[Caja]:
        ordenadas = sorted(cajas, key=lambda b: b[2] * b[3], reverse=True)
        filtradas: List[Caja] = []
        for caja in ordenadas:
            if any(self._es_contenido(caja, ya) or self._iou(caja, ya) > 0.35 for ya in filtradas):
                continue
            filtradas.append(caja)
        return filtradas

    def _detectar_opencv(self, img: np.ndarray) -> List[Caja]:
        alto, ancho = img.shape[:2]
        area_total = alto * ancho
        gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gris, (5, 5), 0)
        bordes = cv2.Canny(blur, 50, 150)

        k_size = max(5, int(min(ancho, alto) * 0.015) | 1)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k_size, k_size))
        cerrado = cv2.morphologyEx(bordes, cv2.MORPH_CLOSE, kernel, iterations=2)
        dilatado = cv2.dilate(cerrado, kernel, iterations=1)
        contornos, _ = cv2.findContours(dilatado, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        candidatos: List[Caja] = []
        for cnt in contornos:
            area = cv2.contourArea(cnt)
            if 0.015 * area_total <= area <= 0.85 * area_total:
                x, y, w, h = cv2.boundingRect(cnt)
                ar = w / float(h) if h > 0 else 0
                if 0.3 <= ar <= 3.5 and w >= 20 and h >= 20:
                    candidatos.append((x, y, w, h))
        return self._suprimir_duplicados(candidatos)

    # ------------------------------------------------------------- Principal
    def analizar_imagen_inventario(self, image_path: str, etiqueta_esperada: str) -> Dict[str, Any]:
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"No se pudo leer la imagen en la ruta: {image_path}")
        alto, ancho = img.shape[:2]

        motor_usado = "opencv"
        scores: List[float] = []
        detecciones: List[Caja] = []

        if self.motor_preferido != "opencv":
            try:
                detecciones, scores = self._detectar_yolo(img)
                motor_usado = "yolo"
            except RuntimeError:
                if self.motor_preferido == "yolo":
                    raise
        if motor_usado == "opencv":
            detecciones = self._detectar_opencv(img)

        # Ordenar de arriba-abajo y de izquierda a derecha para numerar de forma estable
        orden = sorted(range(len(detecciones)), key=lambda i: (detecciones[i][1] // 40, detecciones[i][0]))
        detecciones = [detecciones[i] for i in orden]
        if scores:
            scores = [scores[i] for i in orden]

        imagen_anotada = img.copy()
        grosor = max(2, int(min(ancho, alto) / 400))
        escala = max(0.45, min(ancho, alto) / 1600)
        for idx, (x, y, w, h) in enumerate(detecciones, start=1):
            cv2.rectangle(imagen_anotada, (x, y), (x + w, y + h), (0, 200, 83), grosor)
            cv2.putText(imagen_anotada, f"#{idx}", (x + 3, max(y + 16, 14)),
                        cv2.FONT_HERSHEY_SIMPLEX, escala, (0, 200, 83), max(1, grosor - 1))

        cantidad = len(detecciones)
        nombre_salida = "annotated_" + os.path.basename(image_path)
        cv2.imwrite(os.path.join(self.upload_folder, nombre_salida), imagen_anotada)

        if motor_usado == "yolo":
            # Confianza real: promedio de los scores del modelo
            confianza = round(float(np.mean(scores)) * 100, 2) if scores else 0.0
        else:
            # Respaldo OpenCV: no hay score real; valor estimado y conservador
            confianza = round(min(90.0, 70.0 + cantidad * 0.8), 2) if cantidad > 0 else 0.0

        return {
            "etiqueta_clasificada": etiqueta_esperada,
            "cantidad_detectada": cantidad,
            "confianza_ia": confianza,
            "imagen_procesada": nombre_salida,
            "resolucion": f"{ancho}x{alto}",
            "motor": motor_usado,
        }