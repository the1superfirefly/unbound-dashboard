import subprocess
import logging
import os
import time
from datetime import datetime
from database import db, MetricHistory, AlertLog, ServerConfig
from parser import parse_unbound_stats

logger = logging.getLogger('uad.collector')

def purge_orphan_metrics(app):
    """
    Deletes legacy metric records for server IDs that no longer exist in ServerConfig.
    """
    with app.app_context():
        active_ids = [s.id for s in ServerConfig.query.filter_by(is_active=True).all()]
        if active_ids:
            orphans = MetricHistory.query.filter(~MetricHistory.server_id.in_(active_ids)).delete(synchronize_session=False)
            db.session.commit()
            if orphans > 0:
                logger.info(f"Purged {orphans} orphan metric records from database.")
        else:
            # If no active servers, clear all metrics history to prevent stale aggregations
            MetricHistory.query.delete()
            db.session.commit()

def fetch_and_record_metrics(app):
    """
    Polls defined Unbound servers exclusively via unbound-control stats_noreset.
    Supports direct local execution (like padd.sh) and remote control port 8953.
    """
    with app.app_context():
        servers = ServerConfig.query.filter_by(is_active=True).all()
        if not servers:
            # Default seed for localhost unbound resolver on port 8953
            default_srv = ServerConfig(id='srv-localhost', name='Unbound Local Resolver', host='127.0.0.1', port=8953)
            db.session.add(default_srv)
            db.session.commit()
            servers = [default_srv]

        for server in servers:
            server_id = server.id
            server_name = server.name
            host = server.host
            port = server.port or 8953
            
            logger.info(f"Polling unbound-control for server {server_name} ({host}:{port})...")
            stats_data = None
            
            # Polling Strategy:
            # 1. If localhost / 127.0.0.1, try running `unbound-control stats_noreset` directly (padd.sh standard)
            if host in ['127.0.0.1', 'localhost']:
                try:
                    res = subprocess.run(["unbound-control", "stats_noreset"], capture_output=True, text=True, timeout=5)
                    if res.returncode == 0 and res.stdout:
                        stats_data = parse_unbound_stats(res.stdout)
                except Exception as e:
                    logger.debug(f"Direct unbound-control stats_noreset failed: {e}")
                    
            # 2. If not stats_data yet, try running unbound-control -s host:port stats_noreset
            if not stats_data:
                try:
                    cmd = ["unbound-control", "-s", f"{host}:{port}", "stats_noreset"]
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    if res.returncode == 0 and res.stdout:
                        stats_data = parse_unbound_stats(res.stdout)
                    else:
                        logger.warning(f"Unbound-control returned code {res.returncode} for {host}:{port}: {res.stderr}")
                except Exception as e:
                    logger.error(f"Failed to poll unbound-control on {host}:{port}: {e}")

            if not stats_data:
                # Record server offline alert
                logger.warning(f"Server {server_name} ({host}:{port}) is offline or unbound-control unreachable.")
                alert = AlertLog(
                    server_id=server_id,
                    server_name=server_name,
                    alert_type="Server Offline",
                    severity="critical",
                    message=f"Could not connect to unbound-control on {host}:{port}. Ensure remote-control is enabled on port {port}."
                )
                db.session.add(alert)
                db.session.commit()
                continue

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

            if stats_data['avg_latency'] > 30.0:
                db.session.add(AlertLog(
                    server_id=server_id, server_name=server_name,
                    alert_type="High Latency", severity="warning",
                    message=f"Average latency elevated: {stats_data['avg_latency']} ms"
                ))

            if stats_data['servfail_count'] > 5:
                db.session.add(AlertLog(
                    server_id=server_id, server_name=server_name,
                    alert_type="SERVFAIL Spike", severity="critical",
                    message=f"Detected SERVFAIL spike: {stats_data['servfail_count']} failures"
                ))

        db.session.commit()

def sync_logs_to_github(app):
    """
    Background job running every 30 seconds:
    Commits and pushes logs/server_telemetry.log to GitHub, then purges local logs.
    """
    log_path = os.path.join(app.root_path, 'logs', 'server_telemetry.log')
    if not os.path.exists(log_path) or os.path.getsize(log_path) == 0:
        return

    logger.info("Starting automated 30s GitHub log upload & local purge cycle...")
    try:
        rel_log_path = 'logs/server_telemetry.log'
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        
        cwd = app.root_path
        subprocess.run(["git", "add", rel_log_path], cwd=cwd, check=True)
        commit_res = subprocess.run(["git", "commit", "-m", f"Automated telemetry log sync [{timestamp}]"], cwd=cwd, capture_output=True, text=True)
        
        if commit_res.returncode == 0:
            push_res = subprocess.run(["git", "push", "origin", "main"], cwd=cwd, capture_output=True, text=True, timeout=15)
            if push_res.returncode == 0:
                logger.info("Successfully pushed telemetry log to GitHub! Truncating local log file.")
                with open(log_path, 'w') as f:
                    f.truncate(0)
            else:
                logger.warning(f"Git push failed: {push_res.stderr}")
        else:
            logger.info("No new log changes to commit.")
    except Exception as e:
        logger.error(f"Error syncing logs to GitHub: {e}")
