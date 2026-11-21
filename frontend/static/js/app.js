let rolActual = 'ADMIN';

const titulosVista = {
    dashboard: 'Panel General de Control (Administrador)',
    escaneo: 'Escaneo IA de Estantes (Almacenero)',
    catalogo: 'Catálogo y Comparativa Oficial',
    alertas: 'Centro de Alertas e Inconsistencias',
    fuentes: 'Fuentes Oficiales del Estado, Privados y ONGs'
};

function aplicarPermisosPorRol(rol) {
    rolActual = rol;
    const esAdmin = rol === 'ADMIN';

    document.getElementById('perfil-rol-badge').textContent = rol;
    document.getElementById('perfil-nombre').textContent = esAdmin ? 'Administrador AQP' : 'Almacenero AQP';
    const avatarEl = document.getElementById('perfil-avatar');
    if (avatarEl) {
        avatarEl.src = esAdmin ? '/static/img/avatar_admin.png' : '/static/img/avatar_almacenero.png';
    }

    // Botón de exportar Excel visible solo para Administrador
    const btnExcel = document.getElementById('btn-exportar-excel');
    if (btnExcel) {
        btnExcel.classList.toggle('hidden', !esAdmin);
    }

    // Mostrar/ocultar opciones del menú lateral según rol
    document.querySelectorAll('.nav-item').forEach(btn => {
        const rolPermitido = btn.getAttribute('data-rol');
        if (esAdmin) {
            btn.classList.remove('hidden');
        } else {
            btn.classList.toggle('hidden', rolPermitido !== 'ALMACENERO');
        }
    });

    // Redirigir a la vista inicial correspondiente al rol
    if (esAdmin) {
        const btnDash = document.querySelector('.nav-item[data-vista="dashboard"]');
        mostrarVista('dashboard', btnDash);
    } else {
        const btnEsc = document.querySelector('.nav-item[data-vista="escaneo"]');
        mostrarVista('escaneo', btnEsc);
    }
}

function mostrarVista(id, botonEl = null) {
    if (rolActual === 'ALMACENERO' && id !== 'escaneo') {
        id = 'escaneo';
    }

    document.querySelectorAll('.vista').forEach(v => v.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));

    const sec = document.getElementById('vista-' + id);
    if (sec) sec.classList.add('active');

    if (botonEl) {
        botonEl.classList.add('active');
    } else {
        const fallbackBtn = document.querySelector(`.nav-item[data-vista="${id}"]`);
        if (fallbackBtn) fallbackBtn.classList.add('active');
    }

    document.getElementById('titulo-vista').textContent = titulosVista[id] || 'InventarioVision AQP';
}

function accesoRapido(rol) {
    document.getElementById('login-rol').value = rol;
    document.getElementById('login-usuario').value =
        rol === 'ADMIN' ? 'admin@inventariovision.pe' : 'almacen@inventariovision.pe';
    entrarApp(rol);
}

function entrarApp(rol) {
    localStorage.setItem('sesion_rol', rol);
    document.getElementById('login-screen').classList.add('hidden');
    document.getElementById('app-shell').classList.remove('hidden');
    aplicarPermisosPorRol(rol);
    cargarDashboard();
}

function alternarRolRapido() {
    const nuevoRol = rolActual === 'ADMIN' ? 'ALMACENERO' : 'ADMIN';
    aplicarPermisosPorRol(nuevoRol);
}

function cerrarSesion() {
    localStorage.removeItem('sesion_rol');
    document.getElementById('app-shell').classList.add('hidden');
    document.getElementById('login-screen').classList.remove('hidden');
}

document.getElementById('form-login').addEventListener('submit', (e) => {
    e.preventDefault();
    const rol = document.getElementById('login-rol').value;
    entrarApp(rol);
});

async function cargarDashboard() {
    const resp = await fetch('/api/dashboard');
    const data = await resp.json();

    document.getElementById('kpi-productos').textContent = data.kpis.total_productos;
    document.getElementById('kpi-unidades').textContent = data.kpis.unidades_totales;
    document.getElementById('kpi-valor').textContent = 'S/ ' + data.kpis.valor_inventario_pen.toFixed(2);
    document.getElementById('kpi-alertas').textContent = data.kpis.alertas_pendientes;

    const tbodyProd = document.getElementById('tabla-productos');
    const selectProd = document.getElementById('select-producto-escaneo');
    const productoSeleccionadoPrevio = selectProd.value; // guarda la selección actual
    tbodyProd.innerHTML = '';
    selectProd.innerHTML = '';

    data.productos.forEach(p => {
        tbodyProd.innerHTML += `<tr>
            <td>${p.sku}</td>
            <td>${p.nombre}</td>
            <td>${p.categoria_nombre}</td>
            <td><strong>${p.stock_registrado}</strong></td>
            <td>${p.stock_minimo}</td>
            <td>S/ ${p.precio_unitario.toFixed(2)}</td>
            <td>S/ ${(p.precio_referencia_oficial || 0).toFixed(2)}</td>
            <td>${p.fuente_oficial}</td>
            <td>S/ ${p.valor_inventario.toFixed(2)}</td>
            <td><button class="btn-ghost" onclick="eliminarProducto(${p.id_producto})">Eliminar</button></td>
        </tr>`;
        selectProd.innerHTML += `<option value="${p.id_producto}">${p.sku} - ${p.nombre} (Stock: ${p.stock_registrado})</option>`;
    });

    if (productoSeleccionadoPrevio) {
        selectProd.value = productoSeleccionadoPrevio; // restaura la selección
    }

    const tbodyEsc = document.getElementById('tabla-escaneos');
    tbodyEsc.innerHTML = '';
    data.escaneos.forEach(e => {
        tbodyEsc.innerHTML += `<tr>
            <td>#${e.id_escaneo}</td>
            <td>${e.producto_nombre}</td>
            <td>${e.cantidad_sistema_previa}</td>
            <td>${e.cantidad_detectada_ia}</td>
            <td>${e.diferencia}</td>
            <td>${e.confianza_ia}%</td>
            <td><strong>${e.estado_auditoria}</strong></td>
        </tr>`;
    });

    const listaAlertas = document.getElementById('lista-alertas');
    listaAlertas.innerHTML = '';
    data.alertas.forEach(a => {
        listaAlertas.innerHTML += `<div class="alert-card-item">
            <strong>[${a.severidad}] ${a.tipo_alerta} - ${a.producto_nombre}</strong>
            <p>${a.mensaje}</p>
            <small class="muted-text">${a.fecha_generacion}</small><br>
            <button class="btn-ghost" onclick="resolverAlerta(${a.id_alerta})">Marcar como resuelta</button>
        </div>`;
    });
}

document.getElementById('form-escaneo').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData();
    formData.append('id_producto', document.getElementById('select-producto-escaneo').value);
    formData.append('imagen', document.getElementById('input-imagen').files[0]);

    const resp = await fetch('/api/escanear', { method: 'POST', body: formData });
    const data = await resp.json();

    document.getElementById('mensaje-escaneo').innerHTML = `
        <strong>Producto:</strong> ${data.auditoria.producto}<br>
        <strong>Unidades Detectadas por IA:</strong> ${data.vision.cantidad_detectada} (Confianza: ${data.vision.confianza_ia}%)<br>
        <strong>Stock en Sistema:</strong> ${data.auditoria.stock_sistema}<br>
        <strong>Resultado Auditoría:</strong> ${data.auditoria.estado_auditoria} (Diferencia: ${data.auditoria.diferencia})
    `;
    const refImg = document.getElementById('escaneo-referencia');
    if (refImg) refImg.classList.add('hidden');
    const img = document.getElementById('preview-ia');
    img.src = data.imagen_url;
    img.classList.remove('hidden');
    cargarDashboard();
});

document.getElementById('form-nuevo-producto').addEventListener('submit', async (e) => {
    e.preventDefault();
    const precioUnit = parseFloat(document.getElementById('precio_unitario').value);
    const precioRefRaw = document.getElementById('precio_referencia_oficial').value;
    const fuenteRaw = document.getElementById('fuente_oficial').value.trim();

    const payload = {
        sku: document.getElementById('sku').value.trim(),
        nombre: document.getElementById('nombre').value.trim(),
        id_categoria: parseInt(document.getElementById('id_categoria').value, 10),
        stock_registrado: parseInt(document.getElementById('stock_registrado').value, 10),
        stock_minimo: parseInt(document.getElementById('stock_minimo').value, 10),
        precio_unitario: precioUnit,
        precio_referencia_oficial: precioRefRaw !== '' ? parseFloat(precioRefRaw) : precioUnit,
        fuente_oficial: fuenteRaw !== '' ? fuenteRaw : 'Registro Manual Almacén AQP',
        etiqueta_modelo_ia: document.getElementById('etiqueta_ia').value.trim()
    };

    await fetch('/api/productos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    e.target.reset();
    cargarDashboard();
});

async function sincronizarFuentes() {
    const div = document.getElementById('resultado-fuentes');
    div.innerHTML = 'Consultando APIs oficiales (Datos Abiertos Perú, CCIA, Banco de Alimentos ONG)...';
    const resp = await fetch('/api/sincronizar-fuentes', { method: 'POST' });
    const data = await resp.json();
    let html = `<h4>Sincronización completada (${data.timestamp}) - ${data.total_registros_recuperados} registros recuperados</h4><ul>`;
    data.detalle_fuentes.forEach(f => {
        html += `<li><strong>[${f.tipo}] ${f.entidad}:</strong> Estado ${f.estado} (${f.registros_procesados} registros)</li>`;
    });
    html += '</ul>';
    div.innerHTML = html;
    cargarDashboard();
}

async function eliminarProducto(idProducto) {
    if (!confirm('¿Seguro que deseas eliminar este producto y sus registros asociados?')) return;
    const resp = await fetch(`/api/productos/${idProducto}`, { method: 'DELETE' });
    if (resp.ok) {
        cargarDashboard();
    }
}

async function resolverAlerta(idAlerta) {
    const resp = await fetch(`/api/alertas/${idAlerta}/resolver`, { method: 'POST' });
    if (resp.ok) {
        cargarDashboard();
    }
}

const rolGuardado = localStorage.getItem('sesion_rol');
if (rolGuardado) {
    entrarApp(rolGuardado);
}
