const API_URL = window.location.port === '8080' && window.location.hostname === 'localhost'
  ? 'http://localhost:8000'
  : '/api';

let couriers = [
    { courier_id: 'cour_A', zone: 'centro', active_orders: 1, max_capacity: 3 },
    { courier_id: 'cour_B', zone: 'norte', active_orders: 0, max_capacity: 3 },
    { courier_id: 'cour_C', zone: 'centro', active_orders: 3, max_capacity: 3 },
];
let orderCounter = 234;
let currentConfig = {};

function nowISO() { return new Date().toISOString(); }

document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
        if (tab.dataset.tab === 'config') loadConfig();
        if (tab.dataset.tab === 'status') refreshFullStatus();
        if (tab.dataset.tab === 'couriers') renderCouriersTab();
    });
});

function renderCouriers() {
    const tbody = document.getElementById('couriers-body');
    if (!tbody) return;
    tbody.innerHTML = '';
    couriers.forEach((c, i) => {
        const row = document.createElement('tr');
        const pct = (c.active_orders / c.max_capacity) * 100;
        let color = '#00b894';
        if (pct >= 100) color = '#d63031';
        else if (pct >= 67) color = '#fdcb6e';
        row.innerHTML = `
            <td><strong>${c.courier_id}</strong></td>
            <td><select onchange="updateCourier(${i},'zone',this.value)">
                ${['centro','norte','sur','occidente','oriente'].map(z=>`<option ${c.zone===z?'selected':''}>${z}</option>`).join('')}
            </select></td>
            <td><input type="number" value="${c.active_orders}" min="0" style="width:50px" onchange="updateCourier(${i},'active_orders',parseInt(this.value))"></td>
            <td><input type="number" value="${c.max_capacity}" min="1" style="width:50px" onchange="updateCourier(${i},'max_capacity',parseInt(this.value))"></td>
            <td style="color:${color};font-weight:700">${c.active_orders}/${c.max_capacity}</td>
        `;
        tbody.appendChild(row);
    });
}

function renderCouriersTab() {
    const tbody = document.getElementById('couriers-body2');
    if (!tbody) return;
    tbody.innerHTML = '';
    couriers.forEach((c, i) => {
        const row = document.createElement('tr');
        const pct = (c.active_orders / c.max_capacity) * 100;
        let color = '#00b894';
        if (pct >= 100) color = '#d63031';
        else if (pct >= 67) color = '#fdcb6e';
        row.innerHTML = `
            <td><strong>${c.courier_id}</strong></td>
            <td><select onchange="updateCourier(${i},'zone',this.value)">
                ${['centro','norte','sur','occidente','oriente'].map(z=>`<option ${c.zone===z?'selected':''}>${z}</option>`).join('')}
            </select></td>
            <td><input type="number" value="${c.active_orders}" min="0" style="width:50px" onchange="updateCourier(${i},'active_orders',parseInt(this.value))"></td>
            <td><input type="number" value="${c.max_capacity}" min="1" style="width:50px" onchange="updateCourier(${i},'max_capacity',parseInt(this.value))"></td>
            <td style="color:${color};font-weight:700">${c.active_orders}/${c.max_capacity}</td>
            <td><button class="btn btn-small btn-danger" onclick="removeCourier(${i})">Eliminar</button></td>
        `;
        tbody.appendChild(row);
    });
}

function updateCourier(index, field, value) {
    couriers[index][field] = value;
    renderCouriers();
    renderCouriersTab();
}

function removeCourier(index) {
    couriers.splice(index, 1);
    renderCouriers();
    renderCouriersTab();
}

function addCourier() {
    const id = `cour_${String.fromCharCode(65 + couriers.length)}`;
    couriers.push({ courier_id: id, zone: 'centro', active_orders: 0, max_capacity: 3 });
    renderCouriers();
    renderCouriersTab();
}

function renderResult(result) {
    const container = document.getElementById('results-container');
    if (container.querySelector('.placeholder')) container.innerHTML = '';
    const statusClass = result.status.toLowerCase();
    const div = document.createElement('div');
    div.className = `result-item result-${statusClass}`;
    const reasonsHtml = result.reasons.map(r => `<li><strong>${r.rule}</strong>: ${r.detail}</li>`).join('');
    div.innerHTML = `
        <div class="result-header">
            <strong>${result.order_id}</strong>
            <span class="status-badge badge-${statusClass}">${result.status}</span>
        </div>
        <div class="result-details">
            ${result.assigned_courier ? `<p>Repartidor: <strong>${result.assigned_courier}</strong></p>` : ''}
            ${result.cost != null ? `<p>Costo: <strong>$${result.cost.toLocaleString()} COP</strong></p>` : ''}
            ${result.pricing_status ? `<p>Pricing: <em>${result.pricing_status}</em></p>` : ''}
            <ul class="reasons-list">${reasonsHtml}</ul>
        </div>
    `;
    container.prepend(div);
}

async function sendOrder(orderData) {
    try {
        const resp = await fetch(`${API_URL}/assign`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(orderData)
        });
        const result = await resp.json();
        renderResult(result);
        await refreshCouriersFromBackend();
        await refreshHeaderStatus();
        return result;
    } catch (err) { console.error('Error:', err); }
}

async function submitOrder() {
    orderCounter++;
    await sendOrder({
        order_id: `ord_${String(orderCounter).padStart(5,'0')}`,
        timestamp: nowISO(),
        pickup_zone: document.getElementById('pickup_zone').value,
        distance_km: parseFloat(document.getElementById('distance_km').value),
        priority: document.getElementById('priority').value,
        couriers: couriers,
    });
}

async function simulateBurst() {
    const zone = document.getElementById('pickup_zone').value;
    const distance = parseFloat(document.getElementById('distance_km').value);
    const priority = document.getElementById('priority').value;
    for (let i = 0; i < 6; i++) {
        orderCounter++;
        await sendOrder({
            order_id: `ord_${String(orderCounter).padStart(5,'0')}`,
            timestamp: nowISO(), pickup_zone: zone, distance_km: distance, priority: priority, couriers: couriers,
        });
        await new Promise(r => setTimeout(r, 800));
    }
}

async function resetSystem() {
    await fetch(`${API_URL}/couriers/reset`, { method: 'POST' });
    document.getElementById('results-container').innerHTML = '<p class="placeholder">Los resultados aparecen aqui...</p>';
    couriers.forEach(c => c.active_orders = 0);
    renderCouriers();
    renderCouriersTab();
    await refreshHeaderStatus();
}

async function refreshCouriersFromBackend() {
    try {
        const resp = await fetch(`${API_URL}/couriers`);
        const data = await resp.json();
        if (data && data.length > 0) { couriers = data; renderCouriers(); renderCouriersTab(); }
    } catch (err) { console.error('Error:', err); }
}

async function refreshHeaderStatus() {
    try {
        const resp = await fetch(`${API_URL}/health`);
        const data = await resp.json();
        const cb = document.getElementById('hd-cb');
        const cq = document.getElementById('hd-queue');
        const ct = document.getElementById('hd-containment');
        cb.textContent = `CB: ${data.circuit_breaker_state}`;
        cb.className = 'badge badge-sm ' + (data.circuit_breaker_state === 'closed' ? 'cb-closed' : data.circuit_breaker_state === 'open' ? 'cb-open' : 'cb-half');
        cq.textContent = `Cola: ${data.queue_size}`;
        ct.textContent = `Contencion: ${data.contention_active ? 'ACTIVA' : 'OK'}`;
        ct.className = 'badge badge-sm ' + (data.contention_active ? 'contention-on' : 'contention-off');
    } catch (err) { console.error('Error:', err); }
}

async function loadConfig() {
    try {
        const resp = await fetch(`${API_URL}/config`);
        currentConfig = await resp.json();
        const rules = [
            ['same_zone_preferred','Misma zona primero'],['capacity_check','Verificar capacidad'],
            ['least_loaded','Menor carga primero'],['rate_limit_enabled','Rate limit (sliding window)'],
            ['zone_balancing_enabled','Balanceo de zona'],['containment_enabled','Modo contencion'],
            ['cost_optimization_enabled','Optimizacion de costo'],
        ];
        document.getElementById('config-rules').innerHTML = rules.map(([k,l]) =>
            `<div class="config-item"><label>${l}</label><input type="checkbox" ${currentConfig[k]?'checked':''} onchange="toggleConfig('${k}',this.checked)"></div>`).join('');
        const burst = [
            ['max_orders_per_window','Max pedidos por ventana'],['rate_window_seconds','Ventana (segundos)'],
            ['zone_overflow_threshold','Threshold overflow de zona'],['containment_threshold','Threshold contencion'],
            ['containment_duration_seconds','Duracion contencion (s)'],
        ];
        document.getElementById('config-burst').innerHTML = burst.map(([k,l]) =>
            `<div class="config-item"><label>${l}</label><input type="number" value="${currentConfig[k]}" onchange="toggleConfig('${k}',parseInt(this.value))"></div>`).join('');
        const res = [
            ['base_rate_cop','Tarifa base (COP)'],['per_km_rate_cop','Tarifa por km (COP)'],
            ['circuit_failure_threshold','Fallos para abrir CB'],['circuit_open_duration_seconds','Duracion CB abierto (s)'],
            ['pricing_failure_rate','Tasa de fallo pricing (0-1)'],
        ];
        document.getElementById('config-resilience').innerHTML = res.map(([k,l]) =>
            `<div class="config-item"><label>${l}</label><input type="number" step="0.01" value="${currentConfig[k]}" onchange="toggleConfig('${k}',parseFloat(this.value))"></div>`).join('');
    } catch (err) { console.error('Error loading config:', err); }
}

async function toggleConfig(key, value) {
    await fetch(`${API_URL}/config`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ [key]: value }) });
}

async function initCouriers() {
    const json = document.getElementById('init-couriers-json').value;
    try {
        const data = JSON.parse(json);
        const resp = await fetch(`${API_URL}/couriers/init`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
        const result = await resp.json();
        document.getElementById('init-result').innerHTML = `<p style="color:#00b894">${result.message}</p>`;
        await refreshCouriersFromBackend();
    } catch (err) {
        document.getElementById('init-result').innerHTML = `<p style="color:#d63031">Error: ${err.message}</p>`;
    }
}

async function batchAssign() {
    const count = parseInt(document.getElementById('batch-count').value);
    const zone = document.getElementById('batch-zone').value;
    const orders = [];
    for (let i = 0; i < count; i++) {
        orderCounter++;
        orders.push({
            order_id: `ord_${String(orderCounter).padStart(5,'0')}`,
            timestamp: nowISO(), pickup_zone: zone,
            distance_km: parseFloat((1 + Math.random() * 5).toFixed(1)),
            priority: Math.random() > 0.5 ? 'express' : 'normal',
        });
    }
    try {
        const resp = await fetch(`${API_URL}/assign-batch`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ orders, couriers })
        });
        const result = await resp.json();
        let html = `<p><strong>Estrategia:</strong> ${result.strategy} | <strong>Costo total:</strong> $${result.total_cost.toLocaleString()} COP</p>`;
        html += '<div id="batch-results-list">';
        result.results.forEach(r => {
            const cls = r.status.toLowerCase();
            html += `<div class="result-item result-${cls}"><div class="result-header"><strong>${r.order_id}</strong><span class="status-badge badge-${cls}">${r.status}</span></div><div class="result-details">${r.assigned_courier?`Repartidor: <strong>${r.assigned_courier}</strong>`:''} ${r.cost!=null?`| Costo: $${r.cost.toLocaleString()}`:''}</div></div>`;
        });
        html += '</div>';
        document.getElementById('batch-result').innerHTML = html;
        await refreshCouriersFromBackend();
        await refreshHeaderStatus();
    } catch (err) { console.error('Error:', err); }
}

async function batchCompare() {
    const count = parseInt(document.getElementById('batch-count').value);
    const zone = document.getElementById('batch-zone').value;
    const orders = [];
    for (let i = 0; i < count; i++) {
        orderCounter++;
        orders.push({
            order_id: `ord_${String(orderCounter).padStart(5,'0')}`,
            timestamp: nowISO(), pickup_zone: zone,
            distance_km: parseFloat((1 + Math.random() * 5).toFixed(1)),
            priority: Math.random() > 0.5 ? 'express' : 'normal',
        });
    }
    try {
        const resp = await fetch(`${API_URL}/assign-batch/compare`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ orders, couriers })
        });
        const result = await resp.json();
        let html = '<table class="compare-table"><thead><tr><th>Metrica</th><th>Greedy</th><th>Optimo (Hungaro)</th></tr></thead><tbody>';
        html += `<tr><td>Costo total</td><td class="${result.greedy.total_cost<=result.optimal.total_cost?'compare-better':'compare-worse'}">$${result.greedy.total_cost.toLocaleString()}</td><td class="${result.optimal.total_cost<=result.greedy.total_cost?'compare-better':'compare-worse'}">$${result.optimal.total_cost.toLocaleString()}</td></tr>`;
        html += `<tr><td>Asignados</td><td>${result.greedy.assigned}</td><td>${result.optimal.assigned}</td></tr>`;
        html += `<tr><td>En cola</td><td>${result.greedy.queued}</td><td>${result.optimal.queued}</td></tr>`;
        html += `</tbody></table>`;
        html += `<p>Diferencia de costo: <strong class="${result.cost_difference>0?'compare-better':'compare-worse'}">$${result.cost_difference.toLocaleString()}</strong> (greedy - optimo)</p>`;
        html += `<p>Optimo es ${result.optimal_better?'mejor o igual':'peor'} que greedy</p>`;
        document.getElementById('batch-compare-result').innerHTML = html;
    } catch (err) { console.error('Error:', err); }
}

async function loadRejected() {
    try {
        const resp = await fetch(`${API_URL}/explanations/rejected`);
        const data = await resp.json();
        if (!data || data.length === 0) {
            document.getElementById('rejected-list').innerHTML = '<p class="placeholder">No hay pedidos rechazados.</p>';
            return;
        }
        let html = '';
        data.forEach(r => {
            html += `<div class="rejected-item"><div class="order-id">${r.order_id}</div><div class="timestamp">${r.timestamp}</div><div class="explanation">${r.natural_language_explanation}</div></div>`;
        });
        document.getElementById('rejected-list').innerHTML = html;
    } catch (err) { console.error('Error:', err); }
}

async function searchExplanation() {
    const orderId = document.getElementById('explain-order-id').value.trim();
    if (!orderId) return;
    try {
        const resp = await fetch(`${API_URL}/explanation/${orderId}`);
        if (!resp.ok) {
            const err = await resp.json();
            document.getElementById('explain-detail').innerHTML = `<p style="color:#d63031">${err.detail}</p>`;
            return;
        }
        const data = await resp.json();
        let html = `<div class="rejected-item"><div class="order-id">${data.order_id}</div><div class="timestamp">${data.timestamp}</div><div class="explanation">${data.natural_language_explanation}</div></div>`;
        html += `<pre class="json-output">${JSON.stringify(data, null, 2)}</pre>`;
        document.getElementById('explain-detail').innerHTML = html;
    } catch (err) { console.error('Error:', err); }
}

async function refreshFullStatus() {
    try {
        const resp = await fetch(`${API_URL}/health`);
        const data = await resp.json();
        document.getElementById('status-full').innerHTML = `
            <div class="status-grid">
                <div class="status-item"><div class="value" style="font-size:0.9em">${data.status}</div><div class="label">Status</div></div>
                <div class="status-item"><div class="value" style="font-size:0.9em;color:${data.circuit_breaker_state==='closed'?'#00b894':'#d63031'}">${data.circuit_breaker_state}</div><div class="label">Circuit Breaker</div></div>
                <div class="status-item"><div class="value">${data.circuit_failure_count}</div><div class="label">Fallos CB</div></div>
                <div class="status-item"><div class="value">${data.queue_size}</div><div class="label">Cola</div></div>
                <div class="status-item"><div class="value" style="font-size:0.9em;color:${data.contention_active?'#d63031':'#00b894'}">${data.contention_active?'ACTIVA':'OK'}</div><div class="label">Contencion</div></div>
            </div>
            <pre class="json-output">${JSON.stringify(data, null, 2)}</pre>`;
        const qResp = await fetch(`${API_URL}/queue`);
        const qData = await qResp.json();
        document.getElementById('queue-status').innerHTML = `
            <div class="status-grid">
                <div class="status-item"><div class="value">${qData.size}</div><div class="label">Pedidos en cola</div></div>
                <div class="status-item"><div class="value" style="font-size:0.9em;color:${qData.contention_active?'#d63031':'#00b894'}">${qData.contention_active?'ACTIVA':'OK'}</div><div class="label">Contencion</div></div>
                <div class="status-item"><div class="value">${qData.consecutive_full_count}</div><div class="label">Contador saturacion</div></div>
            </div>
            <pre class="json-output">${JSON.stringify(qData, null, 2)}</pre>`;
        document.getElementById('cb-status').innerHTML = `
            <div class="status-grid">
                <div class="status-item"><div class="value" style="font-size:0.9em;color:${data.circuit_breaker_state==='closed'?'#00b894':'#d63031'}">${data.circuit_breaker_state}</div><div class="label">Estado</div></div>
                <div class="status-item"><div class="value">${data.circuit_failure_count}</div><div class="label">Fallos consecutivos</div></div>
            </div>`;
    } catch (err) { console.error('Error:', err); }
}

document.getElementById('order-form').addEventListener('submit', e => { e.preventDefault(); submitOrder(); });
document.getElementById('burst-btn').addEventListener('click', simulateBurst);
document.getElementById('hd-reset').addEventListener('click', resetSystem);
document.getElementById('add-courier-btn').addEventListener('click', addCourier);
document.getElementById('add-courier-btn2').addEventListener('click', addCourier);
document.getElementById('couriers-refresh').addEventListener('click', refreshCouriersFromBackend);
document.getElementById('couriers-reset').addEventListener('click', resetSystem);
document.getElementById('init-couriers-btn').addEventListener('click', initCouriers);
document.getElementById('batch-assign-btn').addEventListener('click', batchAssign);
document.getElementById('batch-compare-btn').addEventListener('click', batchCompare);
document.getElementById('load-rejected-btn').addEventListener('click', loadRejected);
document.getElementById('explain-search-btn').addEventListener('click', searchExplanation);
document.getElementById('status-refresh').addEventListener('click', refreshFullStatus);
document.getElementById('config-reload-btn').addEventListener('click', loadConfig);

renderCouriers();
loadConfig();
refreshHeaderStatus();
setInterval(refreshHeaderStatus, 5000);
