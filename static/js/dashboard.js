// Unbound Analytics Dashboard Client Script

let queryChartInstance = null;
let cacheChartInstance = null;
let latencyChartInstance = null;
let securityChartInstance = null;
let currentServersCache = [];

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initServerStorage();
    initCharts();
    fetchDashboardData();
    fetchAlerts();

    // Auto refresh every 15s
    setInterval(() => {
        fetchDashboardData();
        fetchAlerts();
    }, 15000);

    // Instant data refresh when server dropdown selection changes
    document.getElementById('serverSelect').addEventListener('change', () => {
        fetchDashboardData();
        fetchAlerts();
    });

    document.getElementById('themeToggleBtn').addEventListener('click', toggleTheme);

    document.getElementById('addServerForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const hiddenId = document.getElementById('serverIdHidden').value;
        const name = document.getElementById('serverName').value;
        const host = document.getElementById('serverHost').value;
        const port = parseInt(document.getElementById('serverPort').value);

        const serverData = {
            id: hiddenId || ('srv-' + Date.now()),
            name: name,
            host: host,
            port: port
        };

        await saveServerBackend(serverData);
        resetServerForm();
    });
});

function formatClientLocalTime(isoStr) {
    if (!isoStr) return '';
    try {
        // Handle ISO string or plain string
        let cleanStr = isoStr;
        if (!cleanStr.endsWith('Z') && !cleanStr.includes('+')) {
            cleanStr += 'Z';
        }
        const d = new Date(cleanStr);
        if (isNaN(d.getTime())) return isoStr;
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
    } catch (e) {
        return isoStr;
    }
}

function initTheme() {
    const savedTheme = localStorage.getItem('uad_theme') || 'dark';
    document.documentElement.setAttribute('data-bs-theme', savedTheme);
    updateThemeIcon(savedTheme);
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-bs-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-bs-theme', next);
    localStorage.setItem('uad_theme', next);
    updateThemeIcon(next);
}

function zoomToChart(cardId) {
    const el = document.getElementById(cardId);
    if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.classList.add('chart-highlight-pulse');
        setTimeout(() => {
            el.classList.remove('chart-highlight-pulse');
        }, 2000);
    }
}

function updateThemeIcon(theme) {
    const icon = document.getElementById('themeIcon');
    if (theme === 'dark') {
        icon.className = 'bi bi-moon-stars-fill';
    } else {
        icon.className = 'bi bi-sun-fill';
    }
}

async function initServerStorage() {
    const select = document.getElementById('serverSelect');
    const currentSelected = select.value;
    select.innerHTML = '<option value="all">All Servers (Aggregated)</option>';
    
    try {
        const servers = await fetch('/api/servers').then(r => r.json());
        currentServersCache = servers;
        servers.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s.id;
            opt.textContent = `${s.name} (${s.host})`;
            select.appendChild(opt);
        });

        if (currentSelected && [...select.options].some(o => o.value === currentSelected)) {
            select.value = currentSelected;
        }
        renderServerManagerTable(servers);
    } catch (e) {
        console.error('Failed to load servers from backend:', e);
    }
}

function renderServerManagerTable(servers) {
    const tbody = document.getElementById('serverManagerTableBody');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (!servers || servers.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-3">No servers configured. Add one below.</td></tr>';
        return;
    }

    servers.forEach(s => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td class="ps-3 fw-semibold">${s.name}</td>
            <td class="text-secondary font-monospace small">${s.host}</td>
            <td class="text-secondary small">${s.port}</td>
            <td class="text-end pe-3">
                <button class="btn btn-xs btn-outline-info me-1 py-1 px-2" onclick="editServer('${s.id}')" title="Edit Server">
                    <i class="bi bi-pencil-square"></i> Edit
                </button>
                <button class="btn btn-xs btn-outline-danger py-1 px-2" onclick="deleteServer('${s.id}', '${s.name}')" title="Delete Server">
                    <i class="bi bi-trash"></i> Delete
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function editServer(id) {
    const srv = currentServersCache.find(s => s.id === id);
    if (!srv) return;

    document.getElementById('serverIdHidden').value = srv.id;
    document.getElementById('serverName').value = srv.name;
    document.getElementById('serverHost').value = srv.host;
    document.getElementById('serverPort').value = srv.port;

    document.getElementById('serverFormTitle').innerHTML = '<i class="bi bi-pencil-square me-1 text-info"></i> Edit Server';
    document.getElementById('saveServerBtn').textContent = 'Update Server';
    document.getElementById('cancelEditBtn').classList.remove('d-none');
}

function resetServerForm() {
    document.getElementById('serverIdHidden').value = '';
    document.getElementById('addServerForm').reset();
    document.getElementById('serverFormTitle').innerHTML = '<i class="bi bi-plus-circle me-1 text-primary"></i> Add New Server';
    document.getElementById('saveServerBtn').textContent = 'Save Server';
    document.getElementById('cancelEditBtn').classList.add('d-none');
}

async function deleteServer(id, name) {
    if (!confirm(`Are you sure you want to delete server "${name}"?`)) return;

    try {
        await fetch(`/api/servers?id=${id}`, { method: 'DELETE' });
        await initServerStorage();
        if (getSelectedServerId() === id) {
            document.getElementById('serverSelect').value = 'all';
        }
        fetchDashboardData();
        fetchAlerts();
    } catch (e) {
        console.error('Failed to delete server:', e);
    }
}

async function clearHistoryData() {
    if (!confirm('Are you sure you want to clear all historical metrics and alert logs?')) return;
    try {
        await fetch('/api/clear-history', { method: 'POST' });
        fetchDashboardData();
        fetchAlerts();
    } catch (e) {
        console.error('Failed to clear history data:', e);
    }
}

async function saveServerBackend(server) {
    try {
        await fetch('/api/servers', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(server)
        });
        await initServerStorage();
        document.getElementById('serverSelect').value = server.id;
        fetchDashboardData();
        fetchAlerts();
    } catch (e) {
        console.error('Failed to save server:', e);
    }
}

function getSelectedServerId() {
    return document.getElementById('serverSelect').value;
}

async function fetchDashboardData() {
    const serverId = getSelectedServerId();
    try {
        const [overviewRes, queryRes, cacheRes, latencyRes, securityRes] = await Promise.all([
            fetch(`/api/overview?server_id=${serverId}`).then(r => r.json()),
            fetch(`/api/query?server_id=${serverId}`).then(r => r.json()),
            fetch(`/api/cache?server_id=${serverId}`).then(r => r.json()),
            fetch(`/api/latency?server_id=${serverId}`).then(r => r.json()),
            fetch(`/api/security?server_id=${serverId}`).then(r => r.json())
        ]);

        if (overviewRes.latest) {
            document.getElementById('statTotalQueries').textContent = (overviewRes.latest.total_queries || 0).toLocaleString();
            document.getElementById('statQPS').textContent = overviewRes.latest.qps || 0;
            document.getElementById('statCacheHitRate').textContent = `${overviewRes.latest.cache_hit_rate || 0}%`;
            document.getElementById('statCacheRatio').textContent = `Hits: ${(overviewRes.latest.cache_hits || 0).toLocaleString()} | Miss: ${(overviewRes.latest.cache_misses || 0).toLocaleString()}`;
            document.getElementById('statAvgLatency').textContent = `${overviewRes.latest.avg_latency || 0} ms`;
            document.getElementById('statP95').textContent = overviewRes.latest.p95_latency || 0;
            document.getElementById('statP99').textContent = overviewRes.latest.p99_latency || 0;
            
            const totalAnomalies = (overviewRes.latest.nxdomain_count || 0) + (overviewRes.latest.servfail_count || 0) + (overviewRes.latest.dnssec_failures || 0);
            document.getElementById('statSecurityAnomalies').textContent = totalAnomalies;
            document.getElementById('statNXDOMAIN').textContent = overviewRes.latest.nxdomain_count || 0;
            document.getElementById('statSERVFAIL').textContent = overviewRes.latest.servfail_count || 0;
        }

        updateCharts(queryRes, cacheRes, latencyRes, securityRes);
    } catch (err) {
        console.error('Error updating dashboard:', err);
    }
}

async function fetchAlerts() {
    const serverId = getSelectedServerId();
    try {
        const alerts = await fetch(`/api/alerts?server_id=${serverId}`).then(r => r.json());
        const tbody = document.getElementById('alertsTableBody');
        tbody.innerHTML = '';
        if (!alerts || alerts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-3">No active alerts recorded for selected server.</td></tr>';
            return;
        }
        alerts.forEach(a => {
            const tr = document.createElement('tr');
            const dateStr = formatClientLocalTime(a.timestamp);
            let sevBadge = '<span class="badge bg-info">INFO</span>';
            if (a.severity === 'warning') sevBadge = '<span class="badge bg-warning text-dark">WARNING</span>';
            if (a.severity === 'critical') sevBadge = '<span class="badge bg-danger">CRITICAL</span>';

            tr.innerHTML = `
                <td class="ps-3 text-secondary small">${dateStr}</td>
                <td><span class="badge bg-secondary bg-opacity-25">${a.server_name}</span></td>
                <td class="fw-semibold">${a.alert_type}</td>
                <td>${sevBadge}</td>
                <td class="text-secondary small">${a.message}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error('Failed to fetch alerts:', err);
    }
}

function initCharts() {
    const chartDefaults = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#94a3b8' } } },
        scales: {
            x: {
                ticks: {
                    color: '#64748b',
                    maxTicksLimit: 8,
                    maxRotation: 0,
                    minRotation: 0
                },
                grid: { color: 'rgba(255,255,255,0.05)' }
            },
            y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(255,255,255,0.05)' } }
        }
    };

    const ctxQuery = document.getElementById('queryChart').getContext('2d');
    queryChartInstance = new Chart(ctxQuery, {
        type: 'line',
        data: { labels: [], datasets: [{ label: 'Interval Query Delta', data: [], borderColor: '#3b82f6', backgroundColor: 'rgba(59, 130, 246, 0.15)', fill: true, tension: 0.3 }] },
        options: chartDefaults
    });

    const ctxCache = document.getElementById('cacheChart').getContext('2d');
    cacheChartInstance = new Chart(ctxCache, {
        type: 'doughnut',
        data: { labels: ['Cache Hits', 'Cache Misses'], datasets: [{ data: [0, 0], backgroundColor: ['#06b6d4', '#f43f5e'], borderWidth: 0 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { color: '#94a3b8' } } } }
    });

    const ctxLatency = document.getElementById('latencyChart').getContext('2d');
    latencyChartInstance = new Chart(ctxLatency, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                { label: 'Avg Latency (ms)', data: [], borderColor: '#f59e0b', tension: 0.3 },
                { label: 'P95 Latency (ms)', data: [], borderColor: '#ef4444', borderDash: [5, 5], tension: 0.3 }
            ]
        },
        options: chartDefaults
    });

    const ctxSec = document.getElementById('securityChart').getContext('2d');
    securityChartInstance = new Chart(ctxSec, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [
                { label: 'NXDOMAIN', data: [], backgroundColor: '#ef4444' },
                { label: 'SERVFAIL', data: [], backgroundColor: '#a855f7' }
            ]
        },
        options: chartDefaults
    });
}

function updateCharts(queryData, cacheData, latencyData, securityData) {
    const localTimestamps = (queryData.timestamps || []).map(formatClientLocalTime);

    if (queryChartInstance) {
        queryChartInstance.data.labels = localTimestamps;
        queryChartInstance.data.datasets[0].data = queryData.queries || [];
        queryChartInstance.update();
    }

    if (cacheChartInstance) {
        const totalHits = cacheData.hits ? cacheData.hits.reduce((a, b) => a + b, 0) : 0;
        const totalMisses = cacheData.misses ? cacheData.misses.reduce((a, b) => a + b, 0) : 0;
        cacheChartInstance.data.datasets[0].data = [totalHits, totalMisses];
        cacheChartInstance.update();
    }

    if (latencyChartInstance) {
        latencyChartInstance.data.labels = localTimestamps;
        latencyChartInstance.data.datasets[0].data = latencyData.avg || [];
        latencyChartInstance.data.datasets[1].data = latencyData.p95 || [];
        latencyChartInstance.update();
    }

    if (securityChartInstance) {
        securityChartInstance.data.labels = localTimestamps;
        securityChartInstance.data.datasets[0].data = securityData.nxdomains || [];
        securityChartInstance.data.datasets[1].data = securityData.servfails || [];
        securityChartInstance.update();
    }
}
