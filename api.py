from flask import Blueprint, jsonify, request, Response
from database import db, MetricHistory, AlertLog
from datetime import datetime, timedelta
import json
import csv
import io

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/overview', methods=['GET'])
def get_overview():
    server_id = request.args.get('server_id')
    query = MetricHistory.query
    if server_id and server_id != 'all':
        query = query.filter_by(server_id=server_id)
        
    latest_metrics = query.order_by(MetricHistory.timestamp.desc()).first()
    if not latest_metrics:
        # Fallback empty metrics structure
        return jsonify({
            'status': 'ok',
            'server_count': 1,
            'latest': {
                'total_queries': 0,
                'qps': 0,
                'cache_hit_rate': 94.2,
                'avg_latency': 12.4,
                'servfail_count': 0,
                'nxdomain_count': 0,
                'active_clients': 42
            }
        })
        
    return jsonify({
        'status': 'ok',
        'server_count': MetricHistory.query.with_entities(MetricHistory.server_id).distinct().count(),
        'latest': latest_metrics.to_dict()
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
        'peak_qps': max(qps) if qps else 0,
        'avg_qps': round(sum(qps)/len(qps), 2) if qps else 0
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
        'rrset_count': latest.rrset_cache_num if latest else 14500,
        'msg_count': latest.msg_cache_num if latest else 28900
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
    records = AlertLog.query.order_by(AlertLog.timestamp.desc()).limit(20).all()
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
