import subprocess
import logging
from datetime import datetime
from database import db, MetricHistory, AlertLog
from parser import parse_unbound_stats, generate_mock_stats

logger = logging.getLogger('uad.collector')

def fetch_and_record_metrics(app, servers=None):
    """
    Polls defined Unbound servers or generates simulated metrics if unreachable/mock.
    """
    with app.app_context():
        if not servers:
            servers = [
                {'id': 'srv-default-1', 'name': 'Unbound Resolver Core', 'host': '127.0.0.1', 'port': 8953, 'use_mock': True},
                {'id': 'srv-default-2', 'name': 'Unbound Secondary Gateway', 'host': '192.168.4.86', 'port': 8953, 'use_mock': True}
            ]
            
        for server in servers:
            server_id = server.get('id', 'srv-unknown')
            server_name = server.get('name', 'Unbound Node')
            use_mock = server.get('use_mock', True)
            host = server.get('host', '127.0.0.1')
            
            stats_data = None
            if not use_mock:
                try:
                    cmd = ["unbound-control", "-s", f"{host}:{server.get('port', 8953)}", "stats_noreset"]
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    if res.returncode == 0 and res.stdout:
                        stats_data = parse_unbound_stats(res.stdout)
                except Exception as e:
                    logger.warning(f"Failed to poll unbound-control on {host}: {e}")
                    
            if not stats_data:
                stats_data = generate_mock_stats(server_id, server_name)
                
            record = MetricHistory(
                server_id=server_id,
                server_name=server_name,
                total_queries=stats_data['total_queries'],
                qps=stats_data['qps'],
                cache_hits=stats_data['cache_hits'],
                cache_misses=stats_data['cache_misses'],
                cache_hit_rate=stats_data['cache_hit_rate'],
                prefetch_hits=stats_data['prefetch_hits'],
                rrset_cache_num=stats_data['rrset_cache_num'],
                msg_cache_num=stats_data['msg_cache_num'],
                avg_latency=stats_data['avg_latency'],
                median_latency=stats_data['median_latency'],
                p90_latency=stats_data['p90_latency'],
                p95_latency=stats_data['p95_latency'],
                p99_latency=stats_data['p99_latency'],
                nxdomain_count=stats_data['nxdomain_count'],
                servfail_count=stats_data['servfail_count'],
                dnssec_failures=stats_data['dnssec_failures'],
                excessive_txt_queries=stats_data['excessive_txt_queries'],
                ipv4_queries=stats_data['ipv4_queries'],
                ipv6_queries=stats_data['ipv6_queries'],
                active_clients=stats_data['active_clients']
            )
            db.session.add(record)
            
            # Anomaly & Threshold Alert checks
            if stats_data['avg_latency'] > 30.0:
                alert = AlertLog(
                    server_id=server_id,
                    server_name=server_name,
                    alert_type="High Latency",
                    severity="warning",
                    message=f"Average latency elevated: {stats_data['avg_latency']} ms"
                )
                db.session.add(alert)
                
            if stats_data['cache_hit_rate'] < 80.0:
                alert = AlertLog(
                    server_id=server_id,
                    server_name=server_name,
                    alert_type="Low Cache Hit Rate",
                    severity="warning",
                    message=f"Cache hit rate dropped to {stats_data['cache_hit_rate']}%"
                )
                db.session.add(alert)
                
            if stats_data['servfail_count'] > 10:
                alert = AlertLog(
                    server_id=server_id,
                    server_name=server_name,
                    alert_type="SERVFAIL Spike",
                    severity="critical",
                    message=f"Detected SERVFAIL spike: {stats_data['servfail_count']} failures"
                )
                db.session.add(alert)
                
        db.session.commit()
