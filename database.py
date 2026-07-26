from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

def init_db(app):
    """Initializes the database with Flask application context and auto-migrates columns."""
    db.init_app(app)
    with app.app_context():
        db.create_all()
        try:
            with db.engine.connect() as conn:
                try:
                    conn.execute(db.text("PRAGMA journal_mode=WAL"))
                    conn.execute(db.text("PRAGMA synchronous=NORMAL"))
                except Exception:
                    pass
                for col in ['qtype_srv', 'qtype_ptr']:
                    try:
                        conn.execute(db.text(f"ALTER TABLE metric_history ADD COLUMN {col} BIGINT DEFAULT 0"))
                        conn.commit()
                    except Exception:
                        pass
                try:
                    conn.execute(db.text("CREATE INDEX IF NOT EXISTS idx_srv_ts ON metric_history(server_id, timestamp)"))
                    conn.commit()
                except Exception:
                    pass
        except Exception:
            pass

class ServerConfig(db.Model):
    __tablename__ = 'server_configs'
    
    id = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    host = db.Column(db.String(128), nullable=False)
    port = db.Column(db.Integer, default=8953)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'host': self.host,
            'port': self.port,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class MetricHistory(db.Model):
    __tablename__ = 'metric_history'
    __table_args__ = (db.Index('idx_srv_ts', 'server_id', 'timestamp'),)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    server_id = db.Column(db.String(64), db.ForeignKey('server_configs.id'), nullable=False, index=True)
    server_name = db.Column(db.String(128), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Core Query Counters
    total_queries = db.Column(db.BigInteger, default=0)
    qps = db.Column(db.Float, default=0.0)

    # Cache Metrics
    cache_hits = db.Column(db.BigInteger, default=0)
    cache_misses = db.Column(db.BigInteger, default=0)
    cache_hit_rate = db.Column(db.Float, default=0.0)
    prefetch_hits = db.Column(db.BigInteger, default=0)
    rrset_cache_num = db.Column(db.BigInteger, default=0)
    msg_cache_num = db.Column(db.BigInteger, default=0)

    # Latency Percentiles (ms rounded to 3 decimal places)
    avg_latency = db.Column(db.Float, default=0.0)
    median_latency = db.Column(db.Float, default=0.0)
    p90_latency = db.Column(db.Float, default=0.0)
    p95_latency = db.Column(db.Float, default=0.0)
    p99_latency = db.Column(db.Float, default=0.0)

    # Security & Anomalies
    nxdomain_count = db.Column(db.BigInteger, default=0)
    servfail_count = db.Column(db.BigInteger, default=0)
    dnssec_failures = db.Column(db.BigInteger, default=0)
    excessive_txt_queries = db.Column(db.BigInteger, default=0)

    # Protocols & Clients
    ipv4_queries = db.Column(db.BigInteger, default=0)
    ipv6_queries = db.Column(db.BigInteger, default=0)
    active_clients = db.Column(db.Integer, default=0)

    # Query Types
    qtype_a = db.Column(db.BigInteger, default=0)
    qtype_aaaa = db.Column(db.BigInteger, default=0)
    qtype_srv = db.Column(db.BigInteger, default=0)
    qtype_ptr = db.Column(db.BigInteger, default=0)
    qtype_txt = db.Column(db.BigInteger, default=0)
    qtype_https = db.Column(db.BigInteger, default=0)
    qtype_other = db.Column(db.BigInteger, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'server_id': self.server_id,
            'server_name': self.server_name,
            'timestamp': self.timestamp.isoformat() + 'Z' if self.timestamp else None,
            'total_queries': self.total_queries,
            'qps': round(self.qps or 0.0, 3),
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'cache_hit_rate': round(self.cache_hit_rate or 0.0, 2),
            'prefetch_hits': self.prefetch_hits,
            'rrset_cache_num': self.rrset_cache_num,
            'msg_cache_num': self.msg_cache_num,
            'avg_latency': round(self.avg_latency or 0.0, 3),
            'median_latency': round(self.median_latency or 0.0, 3),
            'p90_latency': round(self.p90_latency or 0.0, 3),
            'p95_latency': round(self.p95_latency or 0.0, 3),
            'p99_latency': round(self.p99_latency or 0.0, 3),
            'nxdomain_count': self.nxdomain_count,
            'servfail_count': self.servfail_count,
            'dnssec_failures': self.dnssec_failures,
            'excessive_txt_queries': self.excessive_txt_queries,
            'ipv4_queries': self.ipv4_queries,
            'ipv6_queries': self.ipv6_queries,
            'active_clients': self.active_clients,
            'qtype_a': self.qtype_a or 0,
            'qtype_aaaa': self.qtype_aaaa or 0,
            'qtype_srv': self.qtype_srv or 0,
            'qtype_ptr': self.qtype_ptr or 0,
            'qtype_txt': self.qtype_txt or 0,
            'qtype_https': self.qtype_https or 0,
            'qtype_other': self.qtype_other or 0
        }

class AlertLog(db.Model):
    __tablename__ = 'alert_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    server_id = db.Column(db.String(64), db.ForeignKey('server_configs.id'), nullable=False)
    server_name = db.Column(db.String(128), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    alert_type = db.Column(db.String(64), nullable=False)
    severity = db.Column(db.String(32), default='warning')
    message = db.Column(db.Text, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'server_id': self.server_id,
            'server_name': self.server_name,
            'timestamp': self.timestamp.isoformat() + 'Z' if self.timestamp else None,
            'alert_type': self.alert_type,
            'severity': self.severity,
            'message': self.message
        }
