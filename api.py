from flask import Blueprint, jsonify, request, Response
from database import db, MetricHistory, AlertLog, ServerConfig
from sqlalchemy import func
from datetime import datetime, timedelta
import json
import csv
import io

api_bp = Blueprint('api', __name__, url_prefix='/api')

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

@api_bp.route('/overview', methods=['GET'])
def get_overview():
    server_id = request.args.get('server_id')
    server_count = ServerConfig.query.filter_by(is_active=True).count()
    
    if server_id and server_id != 'all':
        latest = MetricHistory.query.filter_by(server_id=server_id).order_by(MetricHistory.timestamp.desc()).first()
        if not latest:
            return jsonify({
                'status': 'ok',
                'server_count': server_count,
                'latest': {
                    'server_id': server_id,
                    'server_name': 'Selected Server',
                    'total_queries': 0, 'qps': 0.0, 'cache_hits': 0, 'cache_misses': 0,
                    'cache_hit_rate': 0.0, 'avg_latency': 0.0, 'p95_latency': 0.0,
                    'p99_latency': 0.0, 'servfail_count': 0, 'nxdomain_count': 0,
                    'dnssec_failures': 0, 'active_clients': 0
                }
            })
        return jsonify({'status': 'ok', 'server_count': server_count, 'latest': latest.to_dict()})

    # Aggregated view across all active servers (latest metric per server)
    subq = db.session.query(
        MetricHistory.server_id,
        func.max(MetricHistory.id).label('max_id')
    ).group_by(MetricHistory.server_id).subquery()

    latest_per_server = db.session.query(MetricHistory).join(
        subq, MetricHistory.id == subq.c.max_id
    ).all()

    if not latest_per_server:
        return jsonify({
            'status': 'ok',
            'server_count': server_count,
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
    total_qps = round(sum(m.qps for m in latest_per_server), 2)
    cache_hits = sum(m.cache_hits for m in latest_per_server)
    cache_misses = sum(m.cache_misses for m in latest_per_server)
    total_cache = cache_hits + cache_misses
    cache_hit_rate = round((cache_hits / total_cache * 100), 2) if total_cache > 0 else 0.0
    avg_latency = round(sum(m.avg_latency for m in latest_per_server) / len(latest_per_server), 2)
    p95_latency = max(m.p95_latency for m in latest_per_server)
    p99_latency = max(m.p99_latency for m in latest_per_server)
    nxdomain_count = sum(m.nxdomain_count for m in latest_per_server)
    servfail_count = sum(m.servfail_count for m in latest_per_server)
    dnssec_failures = sum(m.dnssec_failures for m in latest_per_server)
    active_clients = sum(m.active_clients for m in latest_per_server)

    return jsonify({
        'status': 'ok',
        'server_count': server_count,
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

@api_bp.route('/query', methods=['GET'])
def get_query_analytics():
    server_id = request.args.get('server_id')
    query = MetricHistory.query
    if server_id and server_id != 'all':
        query = query.filter_by(server_id=server_id)
        
    records = query.order_by(MetricHistory.timestamp.desc()).limit(30).all()
    records.reverse()
    
    timestamps = [r.timestamp.strftime('%H:%M:%S') for r in records]
    queries = [r.total_queries for r in records]
    qps = [r.qps for r in records]
    ipv4 = [r.ipv4_queries for r in records]
    ipv6 = [r.ipv6_queries for r in records]
    
    return jsonify({
        'timestamps': timestamps,
        'queries': queries,
        'qps': qps,
        'ipv4': ipv4,
        'ipv6': ipv6,
        'total_sum': sum(queries),
        'peak_qps': max(qps) if qps else 0.0,
        'avg_qps': round(sum(qps)/len(qps), 2) if qps else 0.0
    })

@api_bp.route('/cache', methods=['GET'])
def get_cache_analytics():
    server_id = request.args.get('server_id')
    query = MetricHistory.query
    if server_id and server_id != 'all':
        query = query.filter_by(server_id=server_id)
        
    records = query.order_by(MetricHistory.timestamp.desc()).limit(30).all()
    records.reverse()
    
    timestamps = [r.timestamp.strftime('%H:%M:%S') for r in records]
    hits = [r.cache_hits for r in records]
    misses = [r.cache_misses for r in records]
    hit_rates = [r.cache_hit_rate for r in records]
    prefetch = [r.prefetch_hits for r in records]
    
    latest = records[-1] if records else None
    
    return jsonify({
        'timestamps': timestamps,
        'hits': hits,
        'misses': misses,
        'hit_rates': hit_rates,
        'prefetch': prefetch,
        'rrset_count': latest.rrset_cache_num if latest else 0,
        'msg_count': latest.msg_cache_num if latest else 0
    })

@api_bp.route('/latency', methods=['GET'])
def get_latency_analytics():
    server_id = request.args.get('server_id')
    query = MetricHistory.query
    if server_id and server_id != 'all':
        query = query.filter_by(server_id=server_id)
        
    records = query.order_by(MetricHistory.timestamp.desc()).limit(30).all()
    records.reverse()
    
    timestamps = [r.timestamp.strftime('%H:%M:%S') for r in records]
    avg = [r.avg_latency for r in records]
    p50 = [r.median_latency for r in records]
    p90 = [r.p90_latency for r in records]
    p95 = [r.p95_latency for r in records]
    p99 = [r.p99_latency for r in records]
    
    return jsonify({
        'timestamps': timestamps,
        'avg': avg,
        'p50': p50,
        'p90': p90,
        'p95': p95,
        'p99': p99
    })

@api_bp.route('/security', methods=['GET'])
def get_security_analytics():
    server_id = request.args.get('server_id')
    query = MetricHistory.query
    if server_id and server_id != 'all':
        query = query.filter_by(server_id=server_id)
        
    records = query.order_by(MetricHistory.timestamp.desc()).limit(30).all()
    records.reverse()
    
    timestamps = [r.timestamp.strftime('%H:%M:%S') for r in records]
    nxdomains = [r.nxdomain_count for r in records]
    servfails = [r.servfail_count for r in records]
    dnssec_bogus = [r.dnssec_failures for r in records]
    txt_queries = [r.excessive_txt_queries for r in records]
    
    return jsonify({
        'timestamps': timestamps,
        'nxdomains': nxdomains,
        'servfails': servfails,
        'dnssec_bogus': dnssec_bogus,
        'txt_queries': txt_queries
    })

@api_bp.route('/history', methods=['GET'])
def get_history():
    server_id = request.args.get('server_id')
    limit = request.args.get('limit', 50, type=int)
    
    query = MetricHistory.query
    if server_id and server_id != 'all':
        query = query.filter_by(server_id=server_id)
        
    records = query.order_by(MetricHistory.timestamp.desc()).limit(limit).all()
    return jsonify([r.to_dict() for r in records])

@api_bp.route('/alerts', methods=['GET'])
def get_alerts():
    server_id = request.args.get('server_id')
    query = AlertLog.query
    if server_id and server_id != 'all':
        query = query.filter_by(server_id=server_id)
    records = query.order_by(AlertLog.timestamp.desc()).limit(20).all()
    return jsonify([r.to_dict() for r in records])

@api_bp.route('/export/<fmt>', methods=['GET'])
def export_data(fmt):
    records = MetricHistory.query.order_by(MetricHistory.timestamp.desc()).limit(500).all()
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
