import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Busca .env en la raíz del proyecto (InventarioVision_AQP3\.env) y también en el directorio actual
BASE_DIR = Path(__file__).resolve().parents[3]
load_dotenv(BASE_DIR / ".env")
load_dotenv()


class VisionRecognitionService:
    """
    Servicio de visión para auditoría de inventario:
    - Prioriza API multimodal (Gemini) con salida JSON estructurada para conteo preciso.
    - Mantiene respaldo local con OpenCV si no hay API key o falla la conexión.
    """

    def __init__(self, upload_folder: str):
        self.upload_folder = upload_folder
        os.makedirs(self.upload_folder, exist_ok=True)
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None
        self.model_name = "gemini-3.8-flash"

    @staticmethod
    def _mime_from_path(image_path: str) -> str:
        ext = os.path.splitext(image_path)[1].lower()
        if ext in (".jpg", ".jpeg"):
            return "image/jpeg"
        if ext == ".webp":
            return "image/webp"
        return "image/png"

    def _contar_con_gemini(self, image_path: str, etiqueta_esperada: str) -> Tuple[int, float]:
        import time

        if not self.client:
            raise RuntimeError("GEMINI_API_KEY no configurada en .env")

        img = cv2.imread(image_path)
        if img is None:
            raise RuntimeError(f"No se pudo leer la imagen: {image_path}")

        alto, ancho, _ = img.shape
        max_ancho = 1024
        if ancho > max_ancho:
            nuevo_alto = max(1, int(alto * (max_ancho / float(ancho))))
            img_envio = cv2.resize(img, (max_ancho, nuevo_alto), interpolation=cv2.INTER_AREA)
            ext = os.path.splitext(image_path)[1].lower()
            cod_ext = ".jpg" if ext in (".jpg", ".jpeg") else ".png"
            ok, buf = cv2.imencode(cod_ext, img_envio)
            if not ok:
                raise RuntimeError("No se pudo codificar la imagen redimensionada")
            image_bytes = buf.tobytes()
            mime_type = "image/jpeg" if cod_ext == ".jpg" else "image/png"
        else:
            with open(image_path, "rb") as f:
                image_bytes = f.read()
            mime_type = self._mime_from_path(image_path)

        prompt = (
            f"Eres un auditor estricto de inventario en supermercado/almacén. "
            f"El producto seleccionado para auditar es: '{etiqueta_esperada}'. "
            f"Cuenta ÚNICAMENTE las unidades donde se vea claramente que corresponden "
            f"a ese mismo producto y marca (por ejemplo, si se pide 'Gloria', NO cuentes "
            f"'Laive'; si se pide 'Primor', NO cuentes 'Cocinero' ni 'Mirasol'; si se pide "
            f"'Costeño', NO cuentes 'Faraón', aunque sean del mismo tipo de producto). "
            f"Si en la imagen NO hay unidades del producto/marca solicitado, responde "
            f"con cantidad_detectada: 0. "
            f"Sé muy cuidadoso con unidades alineadas una al lado de la otra. "
            f"Responde SOLO con un JSON válido con este formato exacto: "
            f'{{"cantidad_detectada": <entero>, "confianza_ia": <numero entre 0 y 100>}}'
        )

        for intento in range(2):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=[
                        types.Part.from_bytes(
                            data=image_bytes,
                            mime_type=mime_type,
                        ),
                        prompt,
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                        response_mime_type="application/json",
                    ),
                )
                raw_text = (response.text or "").strip()
                data = json.loads(raw_text)
                cantidad = max(0, int(data.get("cantidad_detectada", 0)))
                confianza_raw = float(data.get("confianza_ia", 95.0))
                confianza = round(max(0.0, min(100.0, confianza_raw)), 2)
                return cantidad, confianza
            except Exception as exc:
                msg = str(exc)
                if intento == 0 and ("503" in msg or "UNAVAILABLE" in msg):
                    time.sleep(0.8)
                    continue
                raise

    def _guardar_imagen_anotada(
        self, img: np.ndarray, image_path: str, etiqueta: str, cantidad: int, confianza: float, modo: str
    ) -> str:
        anotada = img.copy()
        alto, ancho, _ = anotada.shape
        cv2.rectangle(anotada, (0, 0), (ancho, 42), (25, 45, 95), -1)
        texto = f"{etiqueta} | Detectados: {cantidad} | Conf: {confianza}% [{modo}]"
        cv2.putText(
            anotada,
            texto,
            (12, 27),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
        )
        nombre_salida = "annotated_" + os.path.basename(image_path)
        ruta_salida = os.path.join(self.upload_folder, nombre_salida)
        cv2.imwrite(ruta_salida, anotada)
        return nombre_salida

    # --- Respaldo local con OpenCV ---
    @staticmethod
    def _iou(box_a: Tuple[int, int, int, int], box_b: Tuple[int, int, int, int]) -> float:
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
    def _es_contenido(inner: Tuple[int, int, int, int], outer: Tuple[int, int, int, int]) -> bool:
        ix, iy, iw, ih = inner
        ox, oy, ow, oh = outer
        return (
            ix >= ox - 3
            and iy >= oy - 3
            and (ix + iw) <= (ox + ow + 3)
            and (iy + ih) <= (oy + oh + 3)
        )

    def _suprimir_duplicados(
        self, cajas: List[Tuple[int, int, int, int]], iou_umbral: float = 0.45
    ) -> List[Tuple[int, int, int, int]]:
        ordenadas = sorted(cajas, key=lambda b: b[2] * b[3], reverse=True)
        filtradas: List[Tuple[int, int, int, int]] = []
        for caja in ordenadas:
            if any(self._es_contenido(caja, ya) or self._iou(caja, ya) > iou_umbral for ya in filtradas):
                continue
            filtradas.append(caja)
        return filtradas

    def _contar_local_opencv(self, img: np.ndarray) -> Tuple[int, float]:
        alto, ancho, _ = img.shape
        area_total = alto * ancho
        gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gris, (5, 5), 0)
        bordes = cv2.Canny(blur, 50, 140)
        k_size = max(3, int(min(ancho, alto) * 0.005) | 1)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k_size, k_size))
        cerrado = cv2.morphologyEx(bordes, cv2.MORPH_CLOSE, kernel, iterations=1)
        contornos, _ = cv2.findContours(cerrado, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        candidatos: List[Tuple[int, int, int, int]] = []
        for cnt in contornos:
            area = cv2.contourArea(cnt)
            if area_total * 0.003 <= area <= area_total * 0.65:
                x, y, w, h = cv2.boundingRect(cnt)
                if w >= 15 and h >= 15:
                    candidatos.append((x, y, w, h))

        filtradas = self._suprimir_duplicados(candidatos)
        cantidad = len(filtradas)
        confianza = 75.0 if cantidad > 0 else 60.0
        return cantidad, confianza

    def analizar_imagen_inventario(self, image_path: str, etiqueta_esperada: str) -> Dict[str, Any]:
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"No se pudo leer la imagen en la ruta: {image_path}")

        alto, ancho, _ = img.shape

        try:
            cantidad_detectada, confianza = self._contar_con_gemini(image_path, etiqueta_esperada)
            modo = "GEMINI"
        except Exception as exc:
            print(f"\n[AVISO VISION] Falló Gemini, usando OpenCV fallback. Motivo: {exc}\n")
            cantidad_detectada, confianza = self._contar_local_opencv(img)
            modo = "OPENCV-FALLBACK"

        nombre_salida = self._guardar_imagen_anotada(
            img=img,
            image_path=image_path,
            etiqueta=etiqueta_esperada,
            cantidad=cantidad_detectada,
            confianza=confianza,
            modo=modo,
        )

        return {
            "etiqueta_clasificada": etiqueta_esperada,
            "cantidad_detectada": cantidad_detectada,
            "confianza_ia": confianza,
            "imagen_procesada": nombre_salida,
            "resolucion": f"{ancho}x{alto}",
        }