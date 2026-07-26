import os
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class ServerConfig(db.Model):
    __tablename__ = 'server_config'
    
    id = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    host = db.Column(db.String(128), nullable=False)
    port = db.Column(db.Integer, default=8953)
    is_active = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'host': self.host,
            'port': self.port,
            'is_active': self.is_active
        }

class MetricHistory(db.Model):
    __tablename__ = 'metric_history'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    server_id = db.Column(db.String(64), index=True)
    server_name = db.Column(db.String(128))
    
    # Query stats
    total_queries = db.Column(db.Integer, default=0)
    qps = db.Column(db.Float, default=0.0)
    
    # Cache stats
    cache_hits = db.Column(db.Integer, default=0)
    cache_misses = db.Column(db.Integer, default=0)
    cache_hit_rate = db.Column(db.Float, default=0.0)
    prefetch_hits = db.Column(db.Integer, default=0)
    rrset_cache_num = db.Column(db.Integer, default=0)
    msg_cache_num = db.Column(db.Integer, default=0)
    
    # Latency stats (ms)
    avg_latency = db.Column(db.Float, default=0.0)
    median_latency = db.Column(db.Float, default=0.0)
    p90_latency = db.Column(db.Float, default=0.0)
    p95_latency = db.Column(db.Float, default=0.0)
    p99_latency = db.Column(db.Float, default=0.0)
    
    # Security & Error stats
    nxdomain_count = db.Column(db.Integer, default=0)
    servfail_count = db.Column(db.Integer, default=0)
    dnssec_failures = db.Column(db.Integer, default=0)
    excessive_txt_queries = db.Column(db.Integer, default=0)
    
    # Protocol / Misc
    ipv4_queries = db.Column(db.Integer, default=0)
    ipv6_queries = db.Column(db.Integer, default=0)
    active_clients = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'server_id': self.server_id,
            'server_name': self.server_name,
            'total_queries': self.total_queries,
            'qps': self.qps,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'cache_hit_rate': self.cache_hit_rate,
            'prefetch_hits': self.prefetch_hits,
            'rrset_cache_num': self.rrset_cache_num,
            'msg_cache_num': self.msg_cache_num,
            'avg_latency': self.avg_latency,
            'median_latency': self.median_latency,
            'p90_latency': self.p90_latency,
            'p95_latency': self.p95_latency,
            'p99_latency': self.p99_latency,
            'nxdomain_count': self.nxdomain_count,
            'servfail_count': self.servfail_count,
            'dnssec_failures': self.dnssec_failures,
            'excessive_txt_queries': self.excessive_txt_queries,
            'ipv4_queries': self.ipv4_queries,
            'ipv6_queries': self.ipv6_queries,
            'active_clients': self.active_clients
        }

class AlertLog(db.Model):
    __tablename__ = 'alert_log'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    server_id = db.Column(db.String(64))
    server_name = db.Column(db.String(128))
    alert_type = db.Column(db.String(64))
    severity = db.Column(db.String(32))
    message = db.Column(db.Text)

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'server_id': self.server_id,
            'server_name': self.server_name,
            'alert_type': self.alert_type,
            'severity': self.severity,
            'message': self.message
        }

def init_db(app):
    os.makedirs(os.path.join(app.root_path, 'database'), exist_ok=True)
    db_path = os.path.join(app.root_path, 'database', 'unbound_analytics.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
