// Unbound Analytics Dashboard Client Script

let queryChartInstance = null;
let cacheChartInstance = null;
let latencyChartInstance = null;
let securityChartInstance = null;

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
        console.log('Server selected:', getSelectedServerId());
        fetchDashboardData();
        fetchAlerts();
    });

    document.getElementById('themeToggleBtn').addEventListener('click', toggleTheme);

    document.getElementById('addServerForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('serverName').value;
        const host = document.getElementById('serverHost').value;
        const port = parseInt(document.getElementById('serverPort').value);

        const newServer = {
            id: 'srv-' + Date.now(),
            name: name,
            host: host,
            port: port
        };

        await saveServerBackend(newServer);
        bootstrap.Modal.getInstance(document.getElementById('addServerModal')).hide();
        document.getElementById('addServerForm').reset();
    });
});

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
    select.innerHTML = '<option value="all">All Servers (Aggregated)</option>';
    
    try {
        const servers = await fetch('/api/servers').then(r => r.json());
        servers.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s.id;
            opt.textContent = `${s.name} (${s.host})`;
            select.appendChild(opt);
        });
    } catch (e) {
        console.error('Failed to load servers from backend:', e);
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
            const dateStr = new Date(a.timestamp).toLocaleTimeString();
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
            x: { ticks: { color: '#64748b' }, grid: { color: 'rgba(255,255,255,0.05)' } },
            y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(255,255,255,0.05)' } }
        }
    };

    const ctxQuery = document.getElementById('queryChart').getContext('2d');
    queryChartInstance = new Chart(ctxQuery, {
        type: 'line',
        data: { labels: [], datasets: [{ label: 'Queries / min', data: [], borderColor: '#3b82f6', backgroundColor: 'rgba(59, 130, 246, 0.15)', fill: true, tension: 0.3 }] },
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
    if (queryChartInstance) {
        queryChartInstance.data.labels = queryData.timestamps || [];
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
        latencyChartInstance.data.labels = latencyData.timestamps || [];
        latencyChartInstance.data.datasets[0].data = latencyData.avg || [];
        latencyChartInstance.data.datasets[1].data = latencyData.p95 || [];
        latencyChartInstance.update();
    }

    if (securityChartInstance) {
        securityChartInstance.data.labels = securityData.timestamps || [];
        securityChartInstance.data.datasets[0].data = securityData.nxdomains || [];
        securityChartInstance.data.datasets[1].data = securityData.servfails || [];
        securityChartInstance.update();
    }
}
