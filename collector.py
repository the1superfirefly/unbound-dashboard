import subprocess
import logging
import os
import time
from datetime import datetime
from database import db, MetricHistory, AlertLog, ServerConfig
from parser import parse_unbound_stats
from apscheduler.schedulers.background import BackgroundScheduler

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
            MetricHistory.query.delete()
            db.session.commit()

def fetch_and_record_metrics(app):
    """
    Polls defined Unbound servers using unbound-control stats_noreset with correct @port syntax.
    Supports per-server SSL cert configs in certs/<host>/unbound.conf.
    """
    with app.app_context():
        servers = ServerConfig.query.filter_by(is_active=True).all()
        if not servers:
            default_srv = ServerConfig(id='srv-localhost', name='Unbound Local Resolver', host='127.0.0.1', port=8953)
            db.session.add(default_srv)
            db.session.commit()
            servers = [default_srv]

        for server in servers:
            server_id = server.id
            server_name = server.name
            host = server.host
            port = server.port or 8953
            
            logger.info(f"Polling unbound-control for server {server_name} ({host}@{port})...")
            stats_data = None
            last_error = ""
            
            # Check if custom cert config exists for this host
            custom_conf = os.path.join(app.root_path, 'certs', host, 'unbound.conf')
            
            # Polling Variants:
            # 1. Direct local call if host is localhost
            if host in ['127.0.0.1', 'localhost']:
                try:
                    res = subprocess.run(["unbound-control", "stats_noreset"], capture_output=True, text=True, timeout=3)
                    if res.returncode == 0 and res.stdout:
                        stats_data = parse_unbound_stats(res.stdout)
                    else:
                        last_error = res.stderr.strip()
                except Exception as e:
                    last_error = str(e)

            # 2. Custom certificate config if present
            if not stats_data and os.path.exists(custom_conf):
                try:
                    cmd = ["unbound-control", "-c", custom_conf, "-s", f"{host}@{port}", "stats_noreset"]
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                    if res.returncode == 0 and res.stdout:
                        stats_data = parse_unbound_stats(res.stdout)
                    else:
                        last_error = res.stderr.strip()
                except Exception as e:
                    last_error = str(e)
                    
            # 3. Standard remote control with @port syntax (-s host@port)
            if not stats_data:
                try:
                    cmd = ["unbound-control", "-s", f"{host}@{port}", "stats_noreset"]
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                    if res.returncode == 0 and res.stdout:
                        stats_data = parse_unbound_stats(res.stdout)
                    else:
                        last_error = res.stderr.strip() or f"Exit code {res.returncode}"
                except Exception as e:
                    last_error = str(e)

            if not stats_data:
                diag_msg = f"Connection failed to {host}@{port}: {last_error}."
                if "Connection reset by peer" in last_error or "SSL" in last_error or "certificate" in last_error:
                    diag_msg += " SSL cert mismatch. Copy /etc/unbound/unbound_*.pem from target host to certs/" + host + "/."
                elif "Connection refused" in last_error:
                    diag_msg += " Ensure 'control-enable: yes' & 'control-interface: 0.0.0.0' are in /etc/unbound/unbound.conf on target host."
                
                logger.warning(diag_msg)
                alert = AlertLog(
                    server_id=server_id,
                    server_name=server_name,
                    alert_type="Server Offline",
                    severity="critical",
                    message=diag_msg
                )
                db.session.add(alert)
                db.session.commit()
                continue

            logger.info(
                f"[METRIC TELEMETRY] Server '{server_name}' ({host}@{port}) -> "
                f"Total Queries: {stats_data['total_queries']} | QPS: {stats_data['qps']} | "
                f"Hits: {stats_data['cache_hits']} | Misses: {stats_data['cache_misses']} | "
                f"Hit Rate: {stats_data['cache_hit_rate']}% | Avg Latency: {stats_data['avg_latency']}ms | "
                f"SERVFAIL: {stats_data['servfail_count']} | NXDOMAIN: {stats_data['nxdomain_count']}"
            )

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
                avg_latency=round(stats_data['avg_latency'], 3),
                median_latency=round(stats_data['median_latency'], 3),
                p90_latency=round(stats_data['p90_latency'], 3),
                p95_latency=round(stats_data['p95_latency'], 3),
                p99_latency=round(stats_data['p99_latency'], 3),
                nxdomain_count=stats_data['nxdomain_count'],
                servfail_count=stats_data['servfail_count'],
                dnssec_failures=stats_data['dnssec_failures'],
                excessive_txt_queries=stats_data['excessive_txt_queries'],
                ipv4_queries=stats_data['ipv4_queries'],
                ipv6_queries=stats_data['ipv6_queries'],
                active_clients=stats_data['active_clients'],
                qtype_a=stats_data.get('qtype_a', 0),
                qtype_aaaa=stats_data.get('qtype_aaaa', 0),
                qtype_txt=stats_data.get('qtype_txt', 0),
                qtype_https=stats_data.get('qtype_https', 0),
                qtype_other=stats_data.get('qtype_other', 0)
            )
            db.session.add(record)

            if stats_data['avg_latency'] > 30.0:
                db.session.add(AlertLog(
                    server_id=server_id, server_name=server_name,
                    alert_type="High Latency", severity="warning",
                    message=f"Average latency elevated: {round(stats_data['avg_latency'], 3)} ms"
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
        subprocess.run(["git", "add", "-f", rel_log_path], cwd=cwd, check=True)
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

def init_scheduler(app):
    """
    Initializes background scheduler for 1-second metric polling cycles
    and 30-second automated GitHub telemetry log syncs.
    """
    scheduler = BackgroundScheduler(daemon=True)
    
    # 1-second metric collection cycle
    scheduler.add_job(
        func=fetch_and_record_metrics,
        trigger='interval',
        seconds=1,
        args=[app],
        id='metric_collector_job',
        replace_existing=True
    )

    # 30-second log sync cycle to GitHub
    scheduler.add_job(
        func=sync_logs_to_github,
        trigger='interval',
        seconds=30,
        args=[app],
        id='log_sync_job',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("APScheduler initialized: 1s polling cycle & 30s log sync actively running.")
    return scheduler
