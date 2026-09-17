const API_URL = '/api';

let couriers = [
    { courier_id: 'cour_A', zone: 'centro', active_orders: 1, max_capacity: 3 },
    { courier_id: 'cour_B', zone: 'norte', active_orders: 0, max_capacity: 3 },
    { courier_id: 'cour_C', zone: 'centro', active_orders: 3, max_capacity: 3 },
];

let orderCounter = 234;

function nowISO() {
    return new Date().toISOString();
}

function renderCouriers() {
    const tbody = document.getElementById('couriers-body');
    tbody.innerHTML = '';
    couriers.forEach((c, i) => {
        const row = document.createElement('tr');
        const util = `${c.active_orders}/${c.max_capacity}`;
        const pct = (c.active_orders / c.max_capacity) * 100;
        let color = '#00b894';
        if (pct >= 100) color = '#d63031';
        else if (pct >= 67) color = '#fdcb6e';
        row.innerHTML = `
            <td><strong>${c.courier_id}</strong></td>
            <td>
                <select onchange="updateCourier(${i}, 'zone', this.value)">
                    <option ${c.zone==='centro'?'selected':''}>centro</option>
                    <option ${c.zone==='norte'?'selected':''}>norte</option>
                    <option ${c.zone==='sur'?'selected':''}>sur</option>
                    <option ${c.zone==='occidente'?'selected':''}>occidente</option>
                    <option ${c.zone==='oriente'?'selected':''}>oriente</option>
                </select>
            </td>
            <td><input type="number" value="${c.active_orders}" min="0" style="width:50px" onchange="updateCourier(${i}, 'active_orders', parseInt(this.value))"></td>
            <td><input type="number" value="${c.max_capacity}" min="1" style="width:50px" onchange="updateCourier(${i}, 'max_capacity', parseInt(this.value))"></td>
            <td style="color:${color}; font-weight:700">${util}</td>
        `;
        tbody.appendChild(row);
    });
}

function updateCourier(index, field, value) {
    couriers[index][field] = value;
    renderCouriers();
}

function addCourier() {
    const id = `cour_${String.fromCharCode(65 + couriers.length)}`;
    couriers.push({ courier_id: id, zone: 'centro', active_orders: 0, max_capacity: 3 });
    renderCouriers();
}

function renderResult(result) {
    const container = document.getElementById('results-container');
    if (container.querySelector('.placeholder')) {
        container.innerHTML = '';
    }

    const statusClass = result.status.toLowerCase();
    const div = document.createElement('div');
    div.className = `result-item result-${statusClass}`;

    const reasonsHtml = result.reasons.map(r =>
        `<li><strong>${r.rule}</strong>: ${r.detail}</li>`
    ).join('');

    div.innerHTML = `
        <div class="result-header">
            <strong>${result.order_id}</strong>
            <span class="status-badge badge-${statusClass}">${result.status}</span>
        </div>
        <div class="result-details">
            ${result.assigned_courier ? `<p>Repartidor: <strong>${result.assigned_courier}</strong></p>` : ''}
            ${result.cost !== null && result.cost !== undefined ? `<p>Costo: <strong>$${result.cost.toLocaleString()} COP</strong></p>` : ''}
            ${result.pricing_status ? `<p>Pricing: <em>${result.pricing_status}</em></p>` : ''}
            <ul class="reasons-list">${reasonsHtml}</ul>
        </div>
    `;

    container.prepend(div);
}

async function sendOrder(orderData) {
    try {
        const resp = await fetch(`${API_URL}/assign`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(orderData),
        });
        const result = await resp.json();
        renderResult(result);
        await refreshCouriersFromBackend();
        await refreshStatus();
        return result;
    } catch (err) {
        console.error('Error:', err);
    }
}

async function submitOrder() {
    orderCounter++;
    const orderData = {
        order_id: `ord_${String(orderCounter).padStart(5, '0')}`,
        timestamp: nowISO(),
        pickup_zone: document.getElementById('pickup_zone').value,
        distance_km: parseFloat(document.getElementById('distance_km').value),
        priority: document.getElementById('priority').value,
        couriers: couriers,
    };
    await sendOrder(orderData);
}

async function simulateBurst() {
    const zone = document.getElementById('pickup_zone').value;
    const distance = parseFloat(document.getElementById('distance_km').value);
    const priority = document.getElementById('priority').value;

    for (let i = 0; i < 6; i++) {
        orderCounter++;
        const orderData = {
            order_id: `ord_${String(orderCounter).padStart(5, '0')}`,
            timestamp: nowISO(),
            pickup_zone: zone,
            distance_km: distance,
            priority: priority,
            couriers: couriers,
        };
        await sendOrder(orderData);
        await new Promise(r => setTimeout(r, 800));
    }
}

async function resetSystem() {
    await fetch(`${API_URL}/couriers/reset`, { method: 'POST' });
    document.getElementById('results-container').innerHTML = '<p class="placeholder">Los resultados aparecen aqui...</p>';
    couriers.forEach(c => c.active_orders = 0);
    renderCouriers();
    await refreshStatus();
}

async function refreshCouriersFromBackend() {
    try {
        const resp = await fetch(`${API_URL}/couriers`);
        const data = await resp.json();
        if (data && data.length > 0) {
            couriers = data;
            renderCouriers();
        }
    } catch (err) {
        console.error('Error refreshing couriers:', err);
    }
}

async function refreshStatus() {
    try {
        const resp = await fetch(`${API_URL}/health`);
        const data = await resp.json();
        const container = document.getElementById('status-container');
        container.innerHTML = `
            <div class="status-grid">
                <div class="status-item">
                    <div class="value" style="font-size:0.9em">${data.circuit_breaker_state}</div>
                    <div class="label">Circuit Breaker</div>
                </div>
                <div class="status-item">
                    <div class="value">${data.circuit_failure_count}</div>
                    <div class="label">Fallos CB</div>
                </div>
                <div class="status-item">
                    <div class="value">${data.queue_size}</div>
                    <div class="label">Cola</div>
                </div>
                <div class="status-item">
                    <div class="value" style="font-size:0.9em; color:${data.contention_active?'#d63031':'#00b894'}">${data.contention_active ? 'ACTIVA' : 'OK'}</div>
                    <div class="label">Contención</div>
                </div>
            </div>
        `;
    } catch (err) {
        console.error('Error refreshing status:', err);
    }
}

async function loadConfig() {
    try {
        const resp = await fetch(`${API_URL}/config`);
        const cfg = await resp.json();
        const container = document.getElementById('config-container');
        const boolFields = [
            ['same_zone_preferred', 'Misma zona primero'],
            ['capacity_check', 'Verificar capacidad'],
            ['least_loaded', 'Menor carga primero'],
            ['rate_limit_enabled', 'Rate limit (sliding window)'],
            ['zone_balancing_enabled', 'Balanceo de zona'],
            ['containment_enabled', 'Modo contención'],
            ['cost_optimization_enabled', 'Optimización de costo'],
        ];
        container.innerHTML = boolFields.map(([key, label]) => `
            <div class="config-item">
                <label>${label}</label>
                <input type="checkbox" ${cfg[key] ? 'checked' : ''} onchange="toggleConfig('${key}', this.checked)">
            </div>
        `).join('');
    } catch (err) {
        console.error('Error loading config:', err);
    }
}

async function toggleConfig(key, value) {
    await fetch(`${API_URL}/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [key]: value }),
    });
}

document.getElementById('order-form').addEventListener('submit', (e) => {
    e.preventDefault();
    submitOrder();
});
document.getElementById('burst-btn').addEventListener('click', simulateBurst);
document.getElementById('reset-btn').addEventListener('click', resetSystem);
document.getElementById('add-courier-btn').addEventListener('click', addCourier);

renderCouriers();
loadConfig();
refreshStatus();
