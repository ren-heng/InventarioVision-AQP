-- ============================================================================
-- BASE DE DATOS: inventariovision_aqp
-- PROYECTO: InventarioVision AQP - Sistema de Reconocimiento y Control de Inventarios
-- MOTOR: MySQL 8.0+ / MariaDB
-- ============================================================================

CREATE DATABASE IF NOT EXISTS inventariovision_aqp CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE inventariovision_aqp;

-- Tabla: usuarios
CREATE TABLE IF NOT EXISTS usuarios (
    id_usuario INT AUTO_INCREMENT PRIMARY KEY,
    nombre_completo VARCHAR(120) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    rol ENUM('ADMIN', 'ALMACENERO') DEFAULT 'ALMACENERO',
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla: categorias
CREATE TABLE IF NOT EXISTS categorias (
    id_categoria INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(80) NOT NULL UNIQUE,
    descripcion VARCHAR(255)
);

-- Tabla: productos
CREATE TABLE IF NOT EXISTS productos (
    id_producto INT AUTO_INCREMENT PRIMARY KEY,
    sku VARCHAR(30) NOT NULL UNIQUE,
    nombre VARCHAR(150) NOT NULL,
    id_categoria INT NOT NULL,
    stock_registrado INT NOT NULL DEFAULT 0,
    stock_minimo INT NOT NULL DEFAULT 5,
    precio_unitario DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    precio_referencia_oficial DECIMAL(10, 2) DEFAULT NULL,
    fuente_oficial VARCHAR(100) DEFAULT 'MIDAGRI / INEI Datos Abiertos',
    etiqueta_modelo_ia VARCHAR(80) NOT NULL,
    imagen_referencia VARCHAR(255),
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (id_categoria) REFERENCES categorias(id_categoria)
);

-- Tabla: escaneos_inventario
CREATE TABLE IF NOT EXISTS escaneos_inventario (
    id_escaneo INT AUTO_INCREMENT PRIMARY KEY,
    id_producto INT NOT NULL,
    id_usuario INT NOT NULL,
    imagen_analizada VARCHAR(255) NOT NULL,
    cantidad_detectada_ia INT NOT NULL,
    cantidad_sistema_previa INT NOT NULL,
    diferencia INT NOT NULL,
    confianza_ia DECIMAL(5, 2) NOT NULL,
    estado_auditoria ENUM('CONFORME', 'FALTANTE', 'EXCEDENTE') NOT NULL,
    fecha_escaneo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_producto) REFERENCES productos(id_producto),
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
);

-- Tabla: alertas
CREATE TABLE IF NOT EXISTS alertas (
    id_alerta INT AUTO_INCREMENT PRIMARY KEY,
    id_producto INT NOT NULL,
    tipo_alerta ENUM('STOCK_BAJO', 'INCONSISTENCIA_CONTEO', 'VARIACION_PRECIO_OFICIAL') NOT NULL,
    severidad ENUM('ALTA', 'MEDIA', 'BAJA') NOT NULL,
    mensaje TEXT NOT NULL,
    estado ENUM('PENDIENTE', 'RESUELTA') DEFAULT 'PENDIENTE',
    fecha_generacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_producto) REFERENCES productos(id_producto)
);

-- Tabla: fuentes_externas_log (Cumplimiento observación: recuperación automática de fuentes oficiales/ONG)
CREATE TABLE IF NOT EXISTS fuentes_externas_log (
    id_log INT AUTO_INCREMENT PRIMARY KEY,
    entidad_fuente VARCHAR(100) NOT NULL,
    url_endpoint VARCHAR(255) NOT NULL,
    tipo_fuente ENUM('ESTADO_PERU', 'INST_PRIVADA', 'ONG') NOT NULL,
    registros_sincronizados INT DEFAULT 0,
    estado_sincronizacion VARCHAR(50) DEFAULT 'EXITOSO',
    fecha_sincronizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- DATOS SEMILLA (BACKUP INICIAL PARA PRUEBAS EN AREQUIPA)
-- ============================================================================
INSERT INTO usuarios (nombre_completo, email, password_hash, rol) VALUES
('Administrador Almacén AQP', 'admin@inventariovision.pe', 'pbkdf2:sha256:260000$hashdemo123', 'ADMIN'),
('Operador Logístico Miraflores', 'almacen@inventariovision.pe', 'pbkdf2:sha256:260000$hashdemo456', 'ALMACENERO');

INSERT INTO categorias (nombre, descripcion) VALUES
('Abarrotes y Granos', 'Productos de primera necesidad, arroz, azúcar, menestras'),
('Bebidas y Lácteos', 'Leches evaporadas, jugos, aguas embotelladas'),
('Aceites y Conservas', 'Aceites vegetales y conservas de pescado'),
('Limpieza e Higiene', 'Detergentes, jabones y desinfectantes');

INSERT INTO productos (sku, nombre, id_categoria, stock_registrado, stock_minimo, precio_unitario, precio_referencia_oficial, fuente_oficial, etiqueta_modelo_ia) VALUES
('AQP-ARR-001', 'Arroz Extra Costeño 5kg', 1, 45, 15, 22.50, 21.80, 'MIDAGRI - SISAP Arequipa', 'bolsa_arroz'),
('AQP-LEC-002', 'Leche Evaporada Gloria Azul 400g', 2, 120, 30, 4.20, 4.10, 'INEI - Canasta Básica Arequipa', 'lata_leche'),
('AQP-ACE-003', 'Aceite Vegetal Primor 1L', 3, 12, 20, 9.80, 9.50, 'MIDAGRI - Datos Abiertos', 'botella_aceite'),
('AQP-AZU-004', 'Azúcar Rubia Cartavio 5kg', 1, 30, 10, 18.90, 18.50, 'MIDAGRI - SISAP Arequipa', 'bolsa_azucar'),
('AQP-DET-005', 'Detergente Ariel 4kg', 4, 8, 12, 24.00, 23.50, 'SNI / Observatorio Consumo', 'bolsa_detergente');

INSERT INTO escaneos_inventario (id_producto, id_usuario, imagen_analizada, cantidad_detectada_ia, cantidad_sistema_previa, diferencia, confianza_ia, estado_auditoria) VALUES
(1, 2, 'estante_arroz_01.jpg', 45, 45, 0, 96.40, 'CONFORME'),
(2, 2, 'anaquel_leche_02.jpg', 114, 120, -6, 94.15, 'FALTANTE'),
(3, 2, 'gondola_aceite_03.jpg', 12, 12, 0, 92.80, 'CONFORME');

INSERT INTO alertas (id_producto, tipo_alerta, severidad, mensaje, estado) VALUES
(2, 'INCONSISTENCIA_CONTEO', 'ALTA', 'Faltante detectado por visión artificial: Sistema indica 120 unidades de Leche Evaporada Gloria, pero en imagen se detectaron 114 (-6 unidades).', 'PENDIENTE'),
(3, 'STOCK_BAJO', 'MEDIA', 'Stock actual (12 und.) por debajo del mínimo configurado (20 und.) para Aceite Vegetal Primor 1L.', 'PENDIENTE'),
(5, 'STOCK_BAJO', 'ALTA', 'Stock crítico (8 und.) para Detergente Ariel 4kg.');

INSERT INTO fuentes_externas_log (entidad_fuente, url_endpoint, tipo_fuente, registros_sincronizados, estado_sincronizacion) VALUES
('Plataforma Nacional de Datos Abiertos (PCM / MIDAGRI)', 'https://www.datosabiertos.gob.pe/api/3/action/datastore_search', 'ESTADO_PERU', 128, 'EXITOSO'),
('Banco de Alimentos Perú (ONG - Red Arequipa)', 'https://api.bancodealimentosperu.org/v1/canasta-basica', 'ONG', 42, 'EXITOSO'),
('Cámara de Comercio e Industria de Arequipa (CCIA)', 'https://datos.camara-arequipa.org.pe/api/precios-referencia', 'INST_PRIVADA', 65, 'EXITOSO');
