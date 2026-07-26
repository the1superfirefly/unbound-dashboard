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
    fetchDashboardData(true);
    fetchAlerts();

    // Flash-free silent auto-refresh every 1 second
    setInterval(() => {
        fetchDashboardData(false);
        fetchAlerts();
    }, 1000);

    // Instant data refresh when server dropdown selection changes
    document.getElementById('serverSelect').addEventListener('change', (e) => {
        localStorage.setItem('uad_selected_server_id', e.target.value);
        fetchDashboardData(true);
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

function formatClientLocalTime(isoStr, includeDate = false) {
    if (!isoStr) return '';
    try {
        let cleanStr = isoStr;
        if (!cleanStr.endsWith('Z') && !cleanStr.includes('+')) {
            cleanStr += 'Z';
        }
        const d = new Date(cleanStr);
        if (isNaN(d.getTime())) return isoStr;

        if (includeDate) {
            const month = String(d.getMonth() + 1).padStart(2, '0');
            const day = String(d.getDate()).padStart(2, '0');
            const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
            return `${month}/${day} ${time}`;
        }

        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
    } catch (e) {
        return isoStr;
    }
}

function resetZoom(chartType) {
    if (chartType === 'query' && queryChartInstance) queryChartInstance.resetZoom();
    if (chartType === 'latency' && latencyChartInstance) latencyChartInstance.resetZoom();
    if (chartType === 'security' && securityChartInstance) securityChartInstance.resetZoom();
}

async function showMetricDetails(metricType) {
    const serverId = getSelectedServerId();
    const modalEl = new bootstrap.Modal(document.getElementById('metricDetailModal'));
    const titleEl = document.getElementById('metricDetailModalTitle');
    const container = document.getElementById('metricDetailContent');

    container.innerHTML = '<div class="text-center py-4 text-muted"><div class="spinner-border spinner-border-sm me-2 text-primary"></div> Loading meaningful granular breakdown...</div>';
    modalEl.show();

    try {
        const [queryRes, historyData] = await Promise.all([
            fetch(`/api/query?server_id=${serverId}`).then(r => r.json()),
            fetch(`/api/history?server_id=${serverId}&limit=50`).then(r => r.json())
        ]);

        const covInfo = queryRes.time_coverage || {};
        const coverageBadge = `
            <div class="alert alert-dark border border-secondary border-opacity-25 d-flex align-items-center justify-content-between mb-3 py-2 px-3">
                <span class="small text-secondary"><i class="bi bi-clock me-1 text-info"></i> <strong>Time Window Covered:</strong> ${covInfo.coverage_label || '48 Hours'}</span>
                <span class="badge bg-secondary bg-opacity-25 text-light">${covInfo.sample_count || 0} Data Snapshots</span>
            </div>
        `;

        if (metricType === 'queries') {
            titleEl.innerHTML = '<i class="bi bi-bar-chart-line me-2 text-primary"></i> Granular Query Analytics & Top Requested Sites';
            renderQueryDetails(container, historyData, queryRes, coverageBadge);
        } else if (metricType === 'cache') {
            titleEl.innerHTML = '<i class="bi bi-pie-chart me-2 text-info"></i> Granular Cache Efficiency & Top Cached Sites';
            renderCacheDetails(container, historyData, queryRes, coverageBadge);
        } else if (metricType === 'latency') {
            titleEl.innerHTML = '<i class="bi bi-clock-history me-2 text-warning"></i> Granular Latency Percentiles & Response Distribution';
            renderLatencyDetails(container, historyData, coverageBadge);
        } else if (metricType === 'security') {
            titleEl.innerHTML = '<i class="bi bi-shield-exclamation me-2 text-danger"></i> Security Incidents & Anomaly Breakdown';
            renderSecurityDetails(container, historyData, coverageBadge);
        }
    } catch (e) {
        container.innerHTML = `<div class="alert alert-danger mb-0">Failed to load metric details: ${e.message}</div>`;
    }
}

function renderQueryDetails(container, history, queryRes, coverageBadge) {
    if (!history || history.length === 0) {
        container.innerHTML = coverageBadge + '<div class="text-center text-muted py-3">No query metric history recorded yet.</div>';
        return;
    }

    const cachedDomains = queryRes.top_cached_domains || [];
    const fetchedDomains = queryRes.top_fetched_domains || [];

    let cachedRows = '';
    cachedDomains.forEach(d => {
        cachedRows += `
            <tr>
                <td class="ps-3 fw-semibold font-monospace text-light">${d.domain}</td>
                <td class="text-success font-monospace fw-bold">${d.hits} hits</td>
                <td><span class="badge bg-primary bg-opacity-25 text-primary">${d.type}</span></td>
                <td class="text-secondary small">${d.latency}</td>
                <td><span class="badge bg-success bg-opacity-25 text-success">${d.status}</span></td>
            </tr>
        `;
    });

    let fetchedRows = '';
    fetchedDomains.forEach(d => {
        fetchedRows += `
            <tr>
                <td class="ps-3 fw-semibold font-monospace text-light">${d.domain}</td>
                <td class="text-warning font-monospace fw-bold">${d.queries} queries</td>
                <td><span class="badge bg-primary bg-opacity-25 text-primary">${d.type}</span></td>
                <td class="text-secondary small">${d.avg_latency}</td>
                <td><span class="badge bg-warning bg-opacity-25 text-warning">${d.status}</span></td>
            </tr>
        `;
    });

    let historyRows = '';
    history.forEach(h => {
        const timeStr = formatClientLocalTime(h.timestamp, true);
        historyRows += `
            <tr>
                <td class="ps-3 font-monospace small text-secondary">${timeStr}</td>
                <td><span class="badge bg-secondary bg-opacity-25">${h.server_name}</span></td>
                <td class="fw-bold text-light">${h.total_queries.toLocaleString()}</td>
                <td class="text-info">${(h.qps || 0).toFixed(3)}</td>
                <td class="text-secondary">${h.ipv4_queries}</td>
                <td class="text-secondary">${h.ipv6_queries}</td>
                <td class="text-muted">${h.active_clients}</td>
            </tr>
        `;
    });

    container.innerHTML = coverageBadge + `
        <div class="row g-3 mb-4">
            <div class="col-md-3">
                <div class="p-3 rounded bg-body-tertiary border border-secondary border-opacity-25">
                    <small class="text-secondary">Latest Total Queries</small>
                    <h4 class="fw-bold text-light mb-0 mt-1">${(history[0].total_queries || 0).toLocaleString()}</h4>
                </div>
            </div>
            <div class="col-md-3">
                <div class="p-3 rounded bg-body-tertiary border border-secondary border-opacity-25">
                    <small class="text-secondary">Current QPS</small>
                    <h4 class="fw-bold text-primary mb-0 mt-1">${(history[0].qps || 0).toFixed(3)}</h4>
                </div>
            </div>
            <div class="col-md-3">
                <div class="p-3 rounded bg-body-tertiary border border-secondary border-opacity-25">
                    <small class="text-secondary">IPv4 Queries</small>
                    <h4 class="fw-bold text-info mb-0 mt-1">${history[0].ipv4_queries || 0}</h4>
                </div>
            </div>
            <div class="col-md-3">
                <div class="p-3 rounded bg-body-tertiary border border-secondary border-opacity-25">
                    <small class="text-secondary">IPv6 Queries</small>
                    <h4 class="fw-bold text-warning mb-0 mt-1">${history[0].ipv6_queries || 0}</h4>
                </div>
            </div>
        </div>

        <div class="row g-4 mb-4">
            <div class="col-md-6">
                <h6 class="fw-bold text-success mb-2"><i class="bi bi-lightning-charge me-1"></i> Top Sites Served from Cache</h6>
                <div class="table-responsive border border-secondary border-opacity-25 rounded">
                    <table class="table table-dark table-hover align-middle mb-0">
                        <thead>
                            <tr class="text-secondary small">
                                <th class="ps-3">Domain</th>
                                <th>Hits</th>
                                <th>Type</th>
                                <th>Latency</th>
                                <th>Cache Status</th>
                            </tr>
                        </thead>
                        <tbody>${cachedRows}</tbody>
                    </table>
                </div>
            </div>

            <div class="col-md-6">
                <h6 class="fw-bold text-warning mb-2"><i class="bi bi-cloud-arrow-down me-1"></i> Top Upstream Fetched Sites</h6>
                <div class="table-responsive border border-secondary border-opacity-25 rounded">
                    <table class="table table-dark table-hover align-middle mb-0">
                        <thead>
                            <tr class="text-secondary small">
                                <th class="ps-3">Domain</th>
                                <th>Queries</th>
                                <th>Type</th>
                                <th>Avg Latency</th>
                                <th>Resolution</th>
                            </tr>
                        </thead>
                        <tbody>${fetchedRows}</tbody>
                    </table>
                </div>
            </div>
        </div>

        <h6 class="fw-bold text-light mb-2"><i class="bi bi-list-columns me-1"></i> Historical Query Snapshots</h6>
        <div class="table-responsive border border-secondary border-opacity-25 rounded" style="max-height: 250px;">
            <table class="table table-dark table-hover align-middle mb-0">
                <thead>
                    <tr class="text-secondary small">
                        <th class="ps-3">Timestamp</th>
                        <th>Server</th>
                        <th>Cumulative Queries</th>
                        <th>QPS</th>
                        <th>IPv4</th>
                        <th>IPv6</th>
                        <th>Active Clients</th>
                    </tr>
                </thead>
                <tbody>${historyRows}</tbody>
            </table>
        </div>
    `;
}

function renderCacheDetails(container, history, queryRes, coverageBadge) {
    if (!history || history.length === 0) {
        container.innerHTML = coverageBadge + '<div class="text-center text-muted py-3">No cache metric history recorded yet.</div>';
        return;
    }

    const latest = history[0];
    const cachedDomains = queryRes.top_cached_domains || [];

    let cachedRows = '';
    cachedDomains.forEach(d => {
        cachedRows += `
            <tr>
                <td class="ps-3 fw-semibold font-monospace text-light">${d.domain}</td>
                <td class="text-success font-monospace fw-bold">${d.hits} hits</td>
                <td><span class="badge bg-primary bg-opacity-25 text-primary">${d.type}</span></td>
                <td class="text-secondary small">${d.latency}</td>
            </tr>
        `;
    });

    let historyRows = '';
    history.forEach(h => {
        const timeStr = formatClientLocalTime(h.timestamp, true);
        historyRows += `
            <tr>
                <td class="ps-3 font-monospace small text-secondary">${timeStr}</td>
                <td><span class="badge bg-secondary bg-opacity-25">${h.server_name}</span></td>
                <td class="text-success">${h.cache_hits.toLocaleString()}</td>
                <td class="text-danger">${h.cache_misses.toLocaleString()}</td>
                <td class="fw-bold text-info">${h.cache_hit_rate}%</td>
                <td class="text-secondary">${h.prefetch_hits}</td>
                <td class="text-muted">${h.rrset_cache_num}</td>
                <td class="text-muted">${h.msg_cache_num}</td>
            </tr>
        `;
    });

    container.innerHTML = coverageBadge + `
        <div class="row g-3 mb-4">
            <div class="col-md-3">
                <div class="p-3 rounded bg-body-tertiary border border-secondary border-opacity-25">
                    <small class="text-secondary">Hit Rate</small>
                    <h4 class="fw-bold text-info mb-0 mt-1">${latest.cache_hit_rate}%</h4>
                </div>
            </div>
            <div class="col-md-3">
                <div class="p-3 rounded bg-body-tertiary border border-secondary border-opacity-25">
                    <small class="text-secondary">Total Hits</small>
                    <h4 class="fw-bold text-success mb-0 mt-1">${latest.cache_hits.toLocaleString()}</h4>
                </div>
            </div>
            <div class="col-md-3">
                <div class="p-3 rounded bg-body-tertiary border border-secondary border-opacity-25">
                    <small class="text-secondary">Total Misses</small>
                    <h4 class="fw-bold text-danger mb-0 mt-1">${latest.cache_misses.toLocaleString()}</h4>
                </div>
            </div>
            <div class="col-md-3">
                <div class="p-3 rounded bg-body-tertiary border border-secondary border-opacity-25">
                    <small class="text-secondary">Prefetch Hits</small>
                    <h4 class="fw-bold text-warning mb-0 mt-1">${latest.prefetch_hits}</h4>
                </div>
            </div>
        </div>

        <h6 class="fw-bold text-info mb-2"><i class="bi bi-journal-check me-1"></i> Top Cached Domain Entries</h6>
        <div class="table-responsive border border-secondary border-opacity-25 rounded mb-4">
            <table class="table table-dark table-hover align-middle mb-0">
                <thead>
                    <tr class="text-secondary small">
                        <th class="ps-3">Cached Domain</th>
                        <th>Hit Count</th>
                        <th>Record Type</th>
                        <th>Cached Latency</th>
                    </tr>
                </thead>
                <tbody>${cachedRows}</tbody>
            </table>
        </div>

        <h6 class="fw-bold text-light mb-2"><i class="bi bi-list-columns me-1"></i> Historical Cache Performance</h6>
        <div class="table-responsive border border-secondary border-opacity-25 rounded" style="max-height: 250px;">
            <table class="table table-dark table-hover align-middle mb-0">
                <thead>
                    <tr class="text-secondary small">
                        <th class="ps-3">Timestamp</th>
                        <th>Server</th>
                        <th>Hits</th>
                        <th>Misses</th>
                        <th>Hit Rate %</th>
                        <th>Prefetch</th>
                        <th>RRSet Cache</th>
                        <th>Message Cache</th>
                    </tr>
                </thead>
                <tbody>${historyRows}</tbody>
            </table>
        </div>
    `;
}

function renderLatencyDetails(container, history, coverageBadge) {
    if (!history || history.length === 0) {
        container.innerHTML = coverageBadge + '<div class="text-center text-muted py-3">No latency metric history recorded yet.</div>';
        return;
    }

    const latest = history[0];
    let rows = '';
    history.forEach(h => {
        const timeStr = formatClientLocalTime(h.timestamp, true);
        rows += `
            <tr>
                <td class="ps-3 font-monospace small text-secondary">${timeStr}</td>
                <td><span class="badge bg-secondary bg-opacity-25">${h.server_name}</span></td>
                <td class="fw-bold text-warning">${(h.avg_latency || 0).toFixed(3)} ms</td>
                <td class="text-info">${(h.median_latency || 0).toFixed(3)} ms</td>
                <td class="text-secondary">${(h.p90_latency || 0).toFixed(3)} ms</td>
                <td class="text-danger">${(h.p95_latency || 0).toFixed(3)} ms</td>
                <td class="text-danger">${(h.p99_latency || 0).toFixed(3)} ms</td>
            </tr>
        `;
    });

    container.innerHTML = coverageBadge + `
        <div class="row g-3 mb-4">
            <div class="col-md-3">
                <div class="p-3 rounded bg-body-tertiary border border-secondary border-opacity-25">
                    <small class="text-secondary">Avg Latency</small>
                    <h4 class="fw-bold text-warning mb-0 mt-1">${(latest.avg_latency || 0).toFixed(3)} ms</h4>
                </div>
            </div>
            <div class="col-md-3">
                <div class="p-3 rounded bg-body-tertiary border border-secondary border-opacity-25">
                    <small class="text-secondary">P50 (Median)</small>
                    <h4 class="fw-bold text-info mb-0 mt-1">${(latest.median_latency || 0).toFixed(3)} ms</h4>
                </div>
            </div>
            <div class="col-md-3">
                <div class="p-3 rounded bg-body-tertiary border border-secondary border-opacity-25">
                    <small class="text-secondary">P95 Latency</small>
                    <h4 class="fw-bold text-danger mb-0 mt-1">${(latest.p95_latency || 0).toFixed(3)} ms</h4>
                </div>
            </div>
            <div class="col-md-3">
                <div class="p-3 rounded bg-body-tertiary border border-secondary border-opacity-25">
                    <small class="text-secondary">P99 Latency</small>
                    <h4 class="fw-bold text-danger mb-0 mt-1">${(latest.p99_latency || 0).toFixed(3)} ms</h4>
                </div>
            </div>
        </div>

        <h6 class="fw-bold text-light mb-2"><i class="bi bi-list-columns me-1"></i> Latency Percentile Distribution History</h6>
        <div class="table-responsive border border-secondary border-opacity-25 rounded" style="max-height: 350px;">
            <table class="table table-dark table-hover align-middle mb-0">
                <thead>
                    <tr class="text-secondary small">
                        <th class="ps-3">Timestamp</th>
                        <th>Server</th>
                        <th>Avg (ms)</th>
                        <th>P50 Median (ms)</th>
                        <th>P90 (ms)</th>
                        <th>P95 (ms)</th>
                        <th>P99 (ms)</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    `;
}

function renderSecurityDetails(container, history, coverageBadge) {
    if (!history || history.length === 0) {
        container.innerHTML = coverageBadge + '<div class="text-center text-muted py-3">No security incident history recorded yet.</div>';
        return;
    }

    const latest = history[0];
    let rows = '';
    history.forEach(h => {
        const timeStr = formatClientLocalTime(h.timestamp, true);
        rows += `
            <tr>
                <td class="ps-3 font-monospace small text-secondary">${timeStr}</td>
                <td><span class="badge bg-secondary bg-opacity-25">${h.server_name}</span></td>
                <td class="text-danger fw-semibold">${h.nxdomain_count}</td>
                <td class="text-purple fw-semibold">${h.servfail_count}</td>
                <td class="text-warning">${h.dnssec_failures}</td>
                <td class="text-secondary">${h.excessive_txt_queries}</td>
            </tr>
        `;
    });

    container.innerHTML = coverageBadge + `
        <div class="row g-3 mb-4">
            <div class="col-md-3">
                <div class="p-3 rounded bg-body-tertiary border border-secondary border-opacity-25">
                    <small class="text-secondary">NXDOMAIN Count</small>
                    <h4 class="fw-bold text-danger mb-0 mt-1">${latest.nxdomain_count}</h4>
                </div>
            </div>
            <div class="col-md-3">
                <div class="p-3 rounded bg-body-tertiary border border-secondary border-opacity-25">
                    <small class="text-secondary">SERVFAIL Count</small>
                    <h4 class="fw-bold text-warning mb-0 mt-1">${latest.servfail_count}</h4>
                </div>
            </div>
            <div class="col-md-3">
                <div class="p-3 rounded bg-body-tertiary border border-secondary border-opacity-25">
                    <small class="text-secondary">DNSSEC Failures</small>
                    <h4 class="fw-bold text-info mb-0 mt-1">${latest.dnssec_failures}</h4>
                </div>
            </div>
            <div class="col-md-3">
                <div class="p-3 rounded bg-body-tertiary border border-secondary border-opacity-25">
                    <small class="text-secondary">TXT Query Spikes</small>
                    <h4 class="fw-bold text-secondary mb-0 mt-1">${latest.excessive_txt_queries}</h4>
                </div>
            </div>
        </div>

        <h6 class="fw-bold text-light mb-2"><i class="bi bi-list-columns me-1"></i> Security Anomaly Snapshots</h6>
        <div class="table-responsive border border-secondary border-opacity-25 rounded" style="max-height: 350px;">
            <table class="table table-dark table-hover align-middle mb-0">
                <thead>
                    <tr class="text-secondary small">
                        <th class="ps-3">Timestamp</th>
                        <th>Server</th>
                        <th>NXDOMAIN</th>
                        <th>SERVFAIL</th>
                        <th>DNSSEC Bogus</th>
                        <th>TXT Queries</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    `;
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
    const savedServerId = localStorage.getItem('uad_selected_server_id') || 'all';
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

        if ([...select.options].some(o => o.value === savedServerId)) {
            select.value = savedServerId;
        } else {
            select.value = 'all';
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
        fetchDashboardData(true);
        fetchAlerts();
    } catch (e) {
        console.error('Failed to delete server:', e);
    }
}

async function clearHistoryData() {
    if (!confirm('Are you sure you want to clear all historical metrics and alert logs?')) return;
    try {
        await fetch('/api/clear-history', { method: 'POST' });
        fetchDashboardData(true);
        fetchAlerts();
    } catch (e) {
        console.error('Failed to clear history data:', e);
    }
}

async function clearAlerts() {
    if (!confirm('Are you sure you want to clear recent alert logs?')) return;
    const serverId = getSelectedServerId();
    try {
        await fetch(`/api/clear-alerts?server_id=${serverId}`, { method: 'POST' });
        fetchAlerts();
    } catch (e) {
        console.error('Failed to clear alerts:', e);
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
        fetchDashboardData(true);
        fetchAlerts();
    } catch (e) {
        console.error('Failed to save server:', e);
    }
}

function getSelectedServerId() {
    return document.getElementById('serverSelect').value;
}

async function fetchDashboardData(isInitial = false) {
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
            document.getElementById('statQPS').textContent = (overviewRes.latest.qps || 0).toFixed(3);
            document.getElementById('statCacheHitRate').textContent = `${overviewRes.latest.cache_hit_rate || 0}%`;
            document.getElementById('statCacheRatio').textContent = `Hits: ${(overviewRes.latest.cache_hits || 0).toLocaleString()} | Miss: ${(overviewRes.latest.cache_misses || 0).toLocaleString()}`;
            document.getElementById('statAvgLatency').textContent = `${(overviewRes.latest.avg_latency || 0).toFixed(3)} ms`;
            document.getElementById('statP95').textContent = (overviewRes.latest.p95_latency || 0).toFixed(3);
            document.getElementById('statP99').textContent = (overviewRes.latest.p99_latency || 0).toFixed(3);
            
            const totalAnomalies = (overviewRes.latest.nxdomain_count || 0) + (overviewRes.latest.servfail_count || 0) + (overviewRes.latest.dnssec_failures || 0);
            document.getElementById('statSecurityAnomalies').textContent = totalAnomalies;
            document.getElementById('statNXDOMAIN').textContent = overviewRes.latest.nxdomain_count || 0;
            document.getElementById('statSERVFAIL').textContent = overviewRes.latest.servfail_count || 0;
        }

        updateCharts(queryRes, cacheRes, latencyRes, securityRes, isInitial);
    } catch (err) {
        console.error('Error updating dashboard:', err);
    }
}

async function fetchAlerts() {
    const serverId = getSelectedServerId();
    try {
        const alerts = await fetch(`/api/alerts?server_id=${serverId}`).then(r => r.json());
        const tbody = document.getElementById('alertsTableBody');
        if (!tbody) return;
        
        let rowsHtml = '';
        if (!alerts || alerts.length === 0) {
            rowsHtml = '<tr><td colspan="5" class="text-center text-muted py-3">No active alerts recorded for selected server.</td></tr>';
        } else {
            alerts.forEach(a => {
                const dateStr = formatClientLocalTime(a.timestamp, true);
                let sevBadge = '<span class="badge bg-info">INFO</span>';
                if (a.severity === 'warning') sevBadge = '<span class="badge bg-warning text-dark">WARNING</span>';
                if (a.severity === 'critical') sevBadge = '<span class="badge bg-danger">CRITICAL</span>';

                rowsHtml += `
                    <tr>
                        <td class="ps-3 text-secondary small">${dateStr}</td>
                        <td><span class="badge bg-secondary bg-opacity-25">${a.server_name}</span></td>
                        <td class="fw-semibold">${a.alert_type}</td>
                        <td>${sevBadge}</td>
                        <td class="text-secondary small">${a.message}</td>
                    </tr>
                `;
            });
        }

        if (tbody.innerHTML !== rowsHtml) {
            tbody.innerHTML = rowsHtml;
        }
    } catch (err) {
        console.error('Failed to fetch alerts:', err);
    }
}

function initCharts() {
    Chart.defaults.font.family = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
    Chart.defaults.font.size = 11;

    const chartDefaults = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { labels: { color: '#94a3b8', font: { size: 11 } } },
            zoom: {
                zoom: {
                    wheel: { enabled: true },
                    pinch: { enabled: true },
                    mode: 'x'
                },
                pan: {
                    enabled: true,
                    mode: 'x'
                }
            }
        },
        scales: {
            x: {
                ticks: {
                    color: '#64748b',
                    font: { size: 10 },
                    maxTicksLimit: 10,
                    maxRotation: 0,
                    minRotation: 0
                },
                grid: { color: 'rgba(255,255,255,0.05)' }
            },
            y: { ticks: { color: '#64748b', font: { size: 10 } }, grid: { color: 'rgba(255,255,255,0.05)' } }
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

function updateCharts(queryData, cacheData, latencyData, securityData, isInitial = false) {
    const timestamps = queryData.timestamps || [];
    const spanOverMultipleDays = timestamps.length > 0 && (
        new Date(timestamps[timestamps.length - 1]).getDate() !== new Date(timestamps[0]).getDate()
    );

    const localTimestamps = timestamps.map(ts => formatClientLocalTime(ts, spanOverMultipleDays));
    const updateMode = isInitial ? 'default' : 'none'; // 'none' mode prevents flash/animation on 1s refresh

    if (queryChartInstance) {
        queryChartInstance.data.labels = localTimestamps;
        queryChartInstance.data.datasets[0].data = queryData.queries || [];
        queryChartInstance.update(updateMode);
    }

    if (cacheChartInstance) {
        const totalHits = cacheData.hits ? cacheData.hits.reduce((a, b) => a + b, 0) : 0;
        const totalMisses = cacheData.misses ? cacheData.misses.reduce((a, b) => a + b, 0) : 0;
        cacheChartInstance.data.datasets[0].data = [totalHits, totalMisses];
        cacheChartInstance.update(updateMode);
    }

    if (latencyChartInstance) {
        latencyChartInstance.data.labels = localTimestamps;
        latencyChartInstance.data.datasets[0].data = latencyData.avg || [];
        latencyChartInstance.data.datasets[1].data = latencyData.p95 || [];
        latencyChartInstance.update(updateMode);
    }

    if (securityChartInstance) {
        securityChartInstance.data.labels = localTimestamps;
        securityChartInstance.data.datasets[0].data = securityData.nxdomains || [];
        securityChartInstance.data.datasets[1].data = securityData.servfails || [];
        securityChartInstance.update(updateMode);
    }
}
