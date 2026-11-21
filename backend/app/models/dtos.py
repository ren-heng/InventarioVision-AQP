from dataclasses import dataclass, asdict
from typing import Optional

@dataclass
class ProductoDTO:
    id_producto: Optional[int]
    sku: str
    nombre: str
    id_categoria: int
    stock_registrado: int
    stock_minimo: int
    precio_unitario: float
    precio_referencia_oficial: Optional[float]
    fuente_oficial: str
    etiqueta_modelo_ia: str

    def calcular_valor_inventario(self) -> float:
        return round(self.stock_registrado * self.precio_unitario, 2)

    def requiere_reposicion(self) -> bool:
        return self.stock_registrado < self.stock_minimo

    def to_dict(self) -> dict:
        data = asdict(self)
        data["valor_total"] = self.calcular_valor_inventario()
        data["alerta_stock"] = self.requiere_reposicion()
        return data

@dataclass
class ResultadoEscaneoDTO:
    id_producto: int
    producto_nombre: str
    cantidad_sistema: int
    cantidad_detectada: int
    diferencia: int
    confianza_ia: float
    estado_auditoria: str
    alerta_generada: bool
    mensaje_alerta: str
