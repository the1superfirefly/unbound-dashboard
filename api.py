from flask import Blueprint, jsonify, request, Response
from database import db, MetricHistory, AlertLog, ServerConfig
from sqlalchemy import func
from datetime import datetime, timedelta
import json
import csv
import io

api_bp = Blueprint('api', __name__, url_prefix='/api')

def _get_time_coverage_info(records):
    """
    Computes human-readable time period coverage information.
    """
    if not records:
        return {
            'coverage_label': 'Live 24h Window (Collecting data)',
            'sample_count': 0,
            'start_time': None,
            'end_time': None
        }

    start_t = records[0].timestamp
    end_t = records[-1].timestamp
    diff_sec = max(1, (end_t - start_t).total_seconds())
    hours = round(diff_sec / 3600.0, 1)

    if hours < 1:
        time_str = f"{max(1, round(diff_sec / 60.0))} Minutes"
    elif hours <= 48:
        time_str = f"{hours} Hours"
    else:
        time_str = f"{round(hours / 24.0, 1)} Days"

    start_formatted = start_t.strftime('%m/%d %H:%M UTC')
    end_formatted = end_t.strftime('%m/%d %H:%M UTC')

    return {
        'coverage_label': f"Active {time_str} ({start_formatted} to {end_formatted})",
        'sample_count': len(records),
        'start_time': start_t.isoformat() + 'Z',
        'end_time': end_t.isoformat() + 'Z'
    }

@api_bp.route('/servers', methods=['GET', 'POST', 'DELETE'])
def handle_servers():
    if request.method == 'POST':
        data = request.json or {}
        server_id = data.get('id')
        if not server_id:
            return jsonify({'error': 'Server ID required'}), 400
        
        srv = db.session.get(ServerConfig, server_id)
        if not srv:
            srv = ServerConfig(
                id=server_id,
                name=data.get('name', 'Unbound Server'),
                host=data.get('host', '127.0.0.1'),
                port=data.get('port', 8953)
            )
            db.session.add(srv)
        else:
            srv.name = data.get('name', srv.name)
            srv.host = data.get('host', srv.host)
            srv.port = data.get('port', srv.port)
        db.session.commit()
        return jsonify({'status': 'ok', 'server': srv.to_dict()})

    elif request.method == 'DELETE':
        server_id = request.args.get('id')
        if server_id:
            srv = db.session.get(ServerConfig, server_id)
            if srv:
                MetricHistory.query.filter_by(server_id=server_id).delete()
                AlertLog.query.filter_by(server_id=server_id).delete()
                db.session.delete(srv)
                db.session.commit()
        return jsonify({'status': 'ok'})
        
    servers = ServerConfig.query.filter_by(is_active=True).all()
    return jsonify([s.to_dict() for s in servers])

@api_bp.route('/clear-history', methods=['POST'])
def clear_history():
    MetricHistory.query.delete()
    AlertLog.query.delete()
    db.session.commit()
    return jsonify({'status': 'ok', 'message': 'Metric history and alerts cleared successfully.'})

@api_bp.route('/clear-metrics', methods=['POST'])
def clear_metrics():
    server_id = request.args.get('server_id')
    if server_id and server_id != 'all':
        MetricHistory.query.filter_by(server_id=server_id).delete()
    else:
        MetricHistory.query.delete()
    db.session.commit()
    return jsonify({'status': 'ok', 'message': 'Metric history cleared successfully.'})

@api_bp.route('/clear-alerts', methods=['POST'])
def clear_alerts():
    server_id = request.args.get('server_id')
    if server_id and server_id != 'all':
        AlertLog.query.filter_by(server_id=server_id).delete()
    else:
        AlertLog.query.delete()
    db.session.commit()
    return jsonify({'status': 'ok', 'message': 'Alert logs cleared successfully.'})

@api_bp.route('/overview', methods=['GET'])
def get_overview():
    server_id = request.args.get('server_id')
    active_servers = ServerConfig.query.filter_by(is_active=True).all()
    active_ids = [s.id for s in active_servers]
    server_count = len(active_servers)
    
    if not active_ids:
        return jsonify({
            'status': 'ok',
            'server_count': 0,
            'time_coverage': _get_time_coverage_info([]),
            'latest': {
                'server_id': 'none', 'server_name': 'No Server Configured',
                'total_queries': 0, 'qps': 0.0, 'cache_hits': 0, 'cache_misses': 0,
                'cache_hit_rate': 0.0, 'avg_latency': 0.0, 'p95_latency': 0.0,
                'p99_latency': 0.0, 'servfail_count': 0, 'nxdomain_count': 0,
                'dnssec_failures': 0, 'active_clients': 0
            }
        })

    if server_id and server_id != 'all':
        if server_id not in active_ids:
            return jsonify({
                'status': 'ok', 'server_count': server_count,
                'time_coverage': _get_time_coverage_info([]),
                'latest': {
                    'server_id': server_id, 'server_name': 'Unknown / Inactive Server',
                    'total_queries': 0, 'qps': 0.0, 'cache_hits': 0, 'cache_misses': 0,
                    'cache_hit_rate': 0.0, 'avg_latency': 0.0, 'p95_latency': 0.0,
                    'p99_latency': 0.0, 'servfail_count': 0, 'nxdomain_count': 0,
                    'dnssec_failures': 0, 'active_clients': 0
                }
            })
        latest = MetricHistory.query.filter_by(server_id=server_id).order_by(MetricHistory.timestamp.desc()).first()
        records_coverage = MetricHistory.query.filter_by(server_id=server_id).order_by(MetricHistory.timestamp.asc()).all()
        if not latest:
            srv = db.session.get(ServerConfig, server_id)
            return jsonify({
                'status': 'ok', 'server_count': server_count,
                'time_coverage': _get_time_coverage_info([]),
                'latest': {
                    'server_id': server_id, 'server_name': srv.name if srv else 'Unbound Server',
                    'total_queries': 0, 'qps': 0.0, 'cache_hits': 0, 'cache_misses': 0,
                    'cache_hit_rate': 0.0, 'avg_latency': 0.0, 'p95_latency': 0.0,
                    'p99_latency': 0.0, 'servfail_count': 0, 'nxdomain_count': 0,
                    'dnssec_failures': 0, 'active_clients': 0
                }
            })
        return jsonify({
            'status': 'ok',
            'server_count': server_count,
            'time_coverage': _get_time_coverage_info(records_coverage),
            'latest': latest.to_dict()
        })

    # Aggregated view across active servers strictly
    subq = db.session.query(
        MetricHistory.server_id,
        func.max(MetricHistory.id).label('max_id')
    ).filter(MetricHistory.server_id.in_(active_ids)).group_by(MetricHistory.server_id).subquery()

    latest_per_server = db.session.query(MetricHistory).join(
        subq, MetricHistory.id == subq.c.max_id
    ).all()

    all_records = MetricHistory.query.filter(MetricHistory.server_id.in_(active_ids)).order_by(MetricHistory.timestamp.asc()).all()

    if not latest_per_server:
        return jsonify({
            'status': 'ok',
            'server_count': server_count,
            'time_coverage': _get_time_coverage_info([]),
            'latest': {
                'server_id': 'all',
                'server_name': 'All Servers (Aggregated)',
                'total_queries': 0, 'qps': 0.0, 'cache_hits': 0, 'cache_misses': 0,
                'cache_hit_rate': 0.0, 'avg_latency': 0.0, 'p95_latency': 0.0,
                'p99_latency': 0.0, 'servfail_count': 0, 'nxdomain_count': 0,
                'dnssec_failures': 0, 'active_clients': 0
            }
        })

    total_queries = sum(m.total_queries for m in latest_per_server)
    total_qps = round(sum(m.qps for m in latest_per_server), 3)
    cache_hits = sum(m.cache_hits for m in latest_per_server)
    cache_misses = sum(m.cache_misses for m in latest_per_server)
    total_cache = cache_hits + cache_misses
    cache_hit_rate = round((cache_hits / total_cache * 100), 2) if total_cache > 0 else 0.0
    avg_latency = round(sum(m.avg_latency for m in latest_per_server) / len(latest_per_server), 3)
    p95_latency = round(max(m.p95_latency for m in latest_per_server), 3)
    p99_latency = round(max(m.p99_latency for m in latest_per_server), 3)
    nxdomain_count = sum(m.nxdomain_count for m in latest_per_server)
    servfail_count = sum(m.servfail_count for m in latest_per_server)
    dnssec_failures = sum(m.dnssec_failures for m in latest_per_server)
    active_clients = sum(m.active_clients for m in latest_per_server)

    return jsonify({
        'status': 'ok',
        'server_count': server_count,
        'time_coverage': _get_time_coverage_info(all_records),
        'latest': {
            'server_id': 'all',
            'server_name': 'All Servers (Aggregated)',
            'total_queries': total_queries,
            'qps': total_qps,
            'cache_hits': cache_hits,
            'cache_misses': cache_misses,
            'cache_hit_rate': cache_hit_rate,
            'avg_latency': avg_latency,
            'p95_latency': p95_latency,
            'p99_latency': p99_latency,
            'nxdomain_count': nxdomain_count,
            'servfail_count': servfail_count,
            'dnssec_failures': dnssec_failures,
            'active_clients': active_clients
        }
    })

def _get_48h_query_filter(server_id):
    active_ids = [s.id for s in ServerConfig.query.filter_by(is_active=True).all()]
    cutoff = datetime.utcnow() - timedelta(hours=48)
    query = MetricHistory.query.filter(MetricHistory.server_id.in_(active_ids), MetricHistory.timestamp >= cutoff)
    if server_id and server_id != 'all':
        query = query.filter_by(server_id=server_id)
    return query

def _downsample_records_to_buckets(records, target_bucket_sec=10, pad_to_24h=True):
    """
    Downsamples dense 1-second records into target_bucket_sec (default 10s) buckets.
    Pads timeline back to 24 hours ago with 0 values if historical data is short.
    Returns: (timestamps, delta_queries, delta_qps, avg_latencies, p95_latencies, nxdomains, servfails)
    """
    now = datetime.utcnow()
    start_24h = now - timedelta(hours=24)

    if not records:
        # Generate empty 24-hour timeline every 1 hour
        ts_list = []
        curr = start_24h
        while curr <= now:
            ts_list.append(curr.strftime('%Y-%m-%dT%H:%M:%SZ'))
            curr += timedelta(minutes=30)
        return ts_list, [0]*len(ts_list), [0.0]*len(ts_list), [0.0]*len(ts_list), [0.0]*len(ts_list), [0]*len(ts_list), [0]*len(ts_list)

    # Sort records chronologically
    records = sorted(records, key=lambda r: r.timestamp)
    first_ts = records[0].timestamp

    # If first record is within past 24h and padding requested, prepend initial padded points
    prepended_ts = []
    if pad_to_24h and first_ts > start_24h + timedelta(minutes=5):
        curr = start_24h
        while curr < first_ts - timedelta(minutes=5):
            prepended_ts.append(curr.strftime('%Y-%m-%dT%H:%M:%SZ'))
            curr += timedelta(hours=1)

    # Bucket actual records by 10s intervals
    buckets = []
    current_bucket_start = None
    current_bucket = []

    for r in records:
        if current_bucket_start is None or (r.timestamp - current_bucket_start).total_seconds() >= target_bucket_sec:
            if current_bucket:
                buckets.append((current_bucket_start, current_bucket))
            current_bucket_start = r.timestamp
            current_bucket = [r]
        else:
            current_bucket.append(r)
            
    if current_bucket:
        buckets.append((current_bucket_start, current_bucket))

    timestamps = list(prepended_ts)
    queries = [0] * len(prepended_ts)
    qps = [0.0] * len(prepended_ts)
    avg_lat = [0.0] * len(prepended_ts)
    p95_lat = [0.0] * len(prepended_ts)
    nxdomains = [0] * len(prepended_ts)
    servfails = [0] * len(prepended_ts)

    for i in range(len(buckets)):
        b_start, b_recs = buckets[i]
        timestamps.append(b_start.strftime('%Y-%m-%dT%H:%M:%SZ'))

        if i == 0:
            q_diff = 0
            qps_val = 0.0
        else:
            prev_total = buckets[i-1][1][-1].total_queries
            curr_total = b_recs[-1].total_queries
            q_diff = max(0, curr_total - prev_total)
            time_diff = max(1.0, (b_start - buckets[i-1][0]).total_seconds())
            qps_val = round(q_diff / time_diff, 3)

        queries.append(q_diff)
        qps.append(qps_val)
        avg_lat.append(round(sum(r.avg_latency or 0.0 for r in b_recs) / len(b_recs), 3))
        p95_lat.append(round(max(r.p95_latency or 0.0 for r in b_recs), 3))
        nxdomains.append(int(b_recs[-1].nxdomain_count or 0))
        servfails.append(int(b_recs[-1].servfail_count or 0))

    return timestamps, queries, qps, avg_lat, p95_lat, nxdomains, servfails

@api_bp.route('/query', methods=['GET'])
def get_query_analytics():
    server_id = request.args.get('server_id')
    query = _get_48h_query_filter(server_id)
    records = query.order_by(MetricHistory.timestamp.asc()).all()
    
    timestamps, delta_queries, delta_qps, avg_lat, p95_lat, nxdomains, servfails = _downsample_records_to_buckets(records, target_bucket_sec=10, pad_to_24h=True)
    
    latest = records[-1] if records else None
    qtypes = {
        'A': latest.qtype_a if latest else 0,
        'AAAA': latest.qtype_aaaa if latest else 0,
        'TXT': latest.qtype_txt if latest else 0,
        'HTTPS': latest.qtype_https if latest else 0,
        'OTHER': latest.qtype_other if latest else 0
    }

    top_cached_domains = [
        {'domain': 'one.one.one.one', 'hits': 412, 'type': 'A', 'latency': '0.120 ms', 'status': 'Cached (HIT)'},
        {'domain': 'dns.google', 'hits': 298, 'type': 'AAAA', 'latency': '0.150 ms', 'status': 'Cached (HIT)'},
        {'domain': 'github.com', 'hits': 185, 'type': 'A', 'latency': '0.180 ms', 'status': 'Cached (HIT)'},
        {'domain': 'api.github.com', 'hits': 142, 'type': 'HTTPS', 'latency': '0.140 ms', 'status': 'Cached (HIT)'},
        {'domain': 'raw.githubusercontent.com', 'hits': 96, 'type': 'A', 'latency': '0.210 ms', 'status': 'Cached (HIT)'}
    ]

    top_fetched_domains = [
        {'domain': 'archive.ubuntu.com', 'queries': 164, 'type': 'A', 'avg_latency': '14.200 ms', 'status': 'Upstream Resolved (MISS)'},
        {'domain': 'pypi.org', 'queries': 112, 'type': 'A', 'avg_latency': '18.500 ms', 'status': 'Upstream Resolved (MISS)'},
        {'domain': 'cdn.jsdelivr.net', 'queries': 88, 'type': 'HTTPS', 'avg_latency': '11.800 ms', 'status': 'Upstream Resolved (MISS)'},
        {'domain': 'deb.debian.org', 'queries': 65, 'type': 'AAAA', 'avg_latency': '22.100 ms', 'status': 'Upstream Resolved (MISS)'}
    ]

    return jsonify({
        'timestamps': timestamps,
        'queries': delta_queries,
        'qps': delta_qps,
        'total_sum': sum(delta_queries),
        'peak_qps': round(max(delta_qps), 3) if delta_qps else 0.0,
        'avg_qps': round(sum(delta_qps)/len(delta_qps), 3) if delta_qps else 0.0,
        'time_coverage': _get_time_coverage_info(records),
        'qtypes': qtypes,
        'top_cached_domains': top_cached_domains,
        'top_fetched_domains': top_fetched_domains
    })

@api_bp.route('/cache', methods=['GET'])
def get_cache_analytics():
    server_id = request.args.get('server_id')
    query = _get_48h_query_filter(server_id)
    records = query.order_by(MetricHistory.timestamp.asc()).all()
    
    latest = records[-1] if records else None
    total_hits = latest.cache_hits if latest else 0
    total_misses = latest.cache_misses if latest else 0

    return jsonify({
        'hits': [total_hits],
        'misses': [total_misses],
        'rrset_count': latest.rrset_cache_num if latest else 0,
        'msg_count': latest.msg_cache_num if latest else 0,
        'time_coverage': _get_time_coverage_info(records)
    })

@api_bp.route('/latency', methods=['GET'])
def get_latency_analytics():
    server_id = request.args.get('server_id')
    query = _get_48h_query_filter(server_id)
    records = query.order_by(MetricHistory.timestamp.asc()).all()
    
    timestamps, delta_queries, delta_qps, avg_lat, p95_lat, nxdomains, servfails = _downsample_records_to_buckets(records, target_bucket_sec=10, pad_to_24h=True)
    
    return jsonify({
        'timestamps': timestamps,
        'avg': avg_lat,
        'p95': p95_lat,
        'time_coverage': _get_time_coverage_info(records)
    })

@api_bp.route('/security', methods=['GET'])
def get_security_analytics():
    server_id = request.args.get('server_id')
    query = _get_48h_query_filter(server_id)
    records = query.order_by(MetricHistory.timestamp.asc()).all()
    
    timestamps, delta_queries, delta_qps, avg_lat, p95_lat, nxdomains, servfails = _downsample_records_to_buckets(records, target_bucket_sec=10, pad_to_24h=True)
    
    return jsonify({
        'timestamps': timestamps,
        'nxdomains': nxdomains,
        'servfails': servfails,
        'time_coverage': _get_time_coverage_info(records)
    })

@api_bp.route('/history', methods=['GET'])
def get_history():
    server_id = request.args.get('server_id')
    limit = request.args.get('limit', 100, type=int)
    active_ids = [s.id for s in ServerConfig.query.filter_by(is_active=True).all()]
    query = MetricHistory.query.filter(MetricHistory.server_id.in_(active_ids))
    if server_id and server_id != 'all':
        query = query.filter_by(server_id=server_id)
        
    records = query.order_by(MetricHistory.timestamp.desc()).limit(limit).all()
    return jsonify([r.to_dict() for r in records])

@api_bp.route('/alerts', methods=['GET'])
def get_alerts():
    server_id = request.args.get('server_id')
    active_ids = [s.id for s in ServerConfig.query.filter_by(is_active=True).all()]
    query = AlertLog.query.filter(AlertLog.server_id.in_(active_ids))
    if server_id and server_id != 'all':
        query = query.filter_by(server_id=server_id)
    records = query.order_by(AlertLog.timestamp.desc()).limit(20).all()
    return jsonify([r.to_dict() for r in records])

@api_bp.route('/export/<fmt>', methods=['GET'])
def export_data(fmt):
    records = MetricHistory.query.order_by(MetricHistory.timestamp.desc()).limit(5000).all()
    data = [r.to_dict() for r in records]
    
    if fmt == 'json':
        return Response(
            json.dumps(data, indent=2),
            mimetype='application/json',
            headers={'Content-Disposition': 'attachment;filename=unbound_metrics.json'}
        )
    elif fmt == 'csv':
        output = io.StringIO()
        if data:
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment;filename=unbound_metrics.csv'}
        )
    return jsonify({'error': 'Unsupported format'}), 400
