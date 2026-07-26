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

    document.getElementById('serverSelect').addEventListener('change', () => {
        fetchDashboardData();
    });

    document.getElementById('themeToggleBtn').addEventListener('click', toggleTheme);

    document.getElementById('addServerForm').addEventListener('submit', (e) => {
        e.preventDefault();
        const name = document.getElementById('serverName').value;
        const host = document.getElementById('serverHost').value;
        const port = document.getElementById('serverPort').value;
        const useMock = document.getElementById('serverMockMode').checked;

        const newServer = {
            id: 'srv-' + Date.now(),
            name: name,
            host: host,
            port: port,
            useMock: useMock
        };

        saveServer(newServer);
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

function initServerStorage() {
    let servers = JSON.parse(localStorage.getItem('uad_servers') || '[]');
    if (servers.length === 0) {
        servers = [
            { id: 'srv-primary', name: 'Primary Unbound Resolver', host: '192.168.4.86', port: 8953, useMock: true }
        ];
        localStorage.setItem('uad_servers', JSON.stringify(servers));
    }

    const select = document.getElementById('serverSelect');
    select.innerHTML = '<option value="all">All Servers (Aggregated)</option>';
    servers.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s.id;
        opt.textContent = `${s.name} (${s.host})`;
        select.appendChild(opt);
    });
}

function saveServer(server) {
    let servers = JSON.parse(localStorage.getItem('uad_servers') || '[]');
    servers.push(server);
    localStorage.setItem('uad_servers', JSON.stringify(servers));
    initServerStorage();
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
            document.getElementById('statTotalQueries').textContent = overviewRes.latest.total_queries.toLocaleString();
            document.getElementById('statQPS').textContent = overviewRes.latest.qps;
            document.getElementById('statCacheHitRate').textContent = `${overviewRes.latest.cache_hit_rate}%`;
            document.getElementById('statCacheRatio').textContent = `Hits: ${overviewRes.latest.cache_hits.toLocaleString()} | Miss: ${overviewRes.latest.cache_misses.toLocaleString()}`;
            document.getElementById('statAvgLatency').textContent = `${overviewRes.latest.avg_latency} ms`;
            document.getElementById('statP95').textContent = overviewRes.latest.p95_latency;
            document.getElementById('statP99').textContent = overviewRes.latest.p99_latency;
            
            const totalAnomalies = overviewRes.latest.nxdomain_count + overviewRes.latest.servfail_count + overviewRes.latest.dnssec_failures;
            document.getElementById('statSecurityAnomalies').textContent = totalAnomalies;
            document.getElementById('statNXDOMAIN').textContent = overviewRes.latest.nxdomain_count;
            document.getElementById('statSERVFAIL').textContent = overviewRes.latest.servfail_count;
        }

        updateCharts(queryRes, cacheRes, latencyRes, securityRes);
    } catch (err) {
        console.error('Error updating dashboard:', err);
    }
}

async function fetchAlerts() {
    try {
        const alerts = await fetch('/api/alerts').then(r => r.json());
        const tbody = document.getElementById('alertsTableBody');
        tbody.innerHTML = '';
        if (alerts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-3">No active alerts recorded. System healthy.</td></tr>';
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

    // Query Chart
    const ctxQuery = document.getElementById('queryChart').getContext('2d');
    queryChartInstance = new Chart(ctxQuery, {
        type: 'line',
        data: { labels: [], datasets: [{ label: 'Queries / min', data: [], borderColor: '#3b82f6', backgroundColor: 'rgba(59, 130, 246, 0.15)', fill: true, tension: 0.3 }] },
        options: chartDefaults
    });

    // Cache Chart (Doughnut)
    const ctxCache = document.getElementById('cacheChart').getContext('2d');
    cacheChartInstance = new Chart(ctxCache, {
        type: 'doughnut',
        data: { labels: ['Cache Hits', 'Cache Misses'], datasets: [{ data: [90, 10], backgroundColor: ['#06b6d4', '#f43f5e'], borderWidth: 0 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { color: '#94a3b8' } } } }
    });

    // Latency Chart
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

    // Security Chart
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
    if (queryChartInstance && queryData.timestamps) {
        queryChartInstance.data.labels = queryData.timestamps;
        queryChartInstance.data.datasets[0].data = queryData.queries;
        queryChartInstance.update();
    }

    if (cacheChartInstance && cacheData.hits) {
        const totalHits = cacheData.hits.reduce((a, b) => a + b, 0);
        const totalMisses = cacheData.misses.reduce((a, b) => a + b, 0);
        cacheChartInstance.data.datasets[0].data = [totalHits, totalMisses];
        cacheChartInstance.update();
    }

    if (latencyChartInstance && latencyData.timestamps) {
        latencyChartInstance.data.labels = latencyData.timestamps;
        latencyChartInstance.data.datasets[0].data = latencyData.avg;
        latencyChartInstance.data.datasets[1].data = latencyData.p95;
        latencyChartInstance.update();
    }

    if (securityChartInstance && securityData.timestamps) {
        securityChartInstance.data.labels = securityData.timestamps;
        securityChartInstance.data.datasets[0].data = securityData.nxdomains;
        securityChartInstance.data.datasets[1].data = securityData.servfails;
        securityChartInstance.update();
    }
}
