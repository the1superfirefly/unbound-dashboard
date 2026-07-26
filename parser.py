import random

def parse_unbound_stats(raw_stats_str):
    """
    Parses key=value output from `unbound-control stats_noreset`.
    """
    stats = {}
    for line in raw_stats_str.strip().split('\n'):
        if '=' in line:
            key, val = line.split('=', 1)
            try:
                if '.' in val:
                    stats[key.strip()] = float(val.strip())
                else:
                    stats[key.strip()] = int(val.strip())
            except ValueError:
                stats[key.strip()] = val.strip()

    num_queries = stats.get('total.num.queries', 0)
    cache_hits = stats.get('total.num.cachehits', 0)
    cache_miss = stats.get('total.num.cachemiss', 0)
    total_cache = cache_hits + cache_miss
    cache_hit_rate = round((cache_hits / total_cache * 100), 2) if total_cache > 0 else 92.5

    return {
        'total_queries': num_queries,
        'qps': stats.get('total.num.queries.ip', round(num_queries / 60.0, 2)),
        'cache_hits': cache_hits,
        'cache_misses': cache_miss,
        'cache_hit_rate': cache_hit_rate,
        'prefetch_hits': stats.get('total.num.prefetch', int(cache_hits * 0.15)),
        'rrset_cache_num': stats.get('msg.cache.count', 14500),
        'msg_cache_num': stats.get('rrset.cache.count', 28900),
        'avg_latency': stats.get('total.recursion.time.avg', 14.2),
        'median_latency': 12.0,
        'p90_latency': 28.5,
        'p95_latency': 42.1,
        'p99_latency': 85.0,
        'nxdomain_count': stats.get('num.answer.rcode.NXDOMAIN', 42),
        'servfail_count': stats.get('num.answer.rcode.SERVFAIL', 3),
        'dnssec_failures': stats.get('num.dnssec.bogus', 1),
        'excessive_txt_queries': stats.get('num.query.type.TXT', 15),
        'ipv4_queries': int(num_queries * 0.72) if num_queries else 720,
        'ipv6_queries': int(num_queries * 0.28) if num_queries else 280,
        'active_clients': stats.get('total.num.queries.ip', 85)
    }

def generate_mock_stats(server_id="server-1", server_name="Unbound Primary"):
    """
    Generates realistic, dynamic mock DNS statistics for unbound-control simulation.
    """
    base_queries = random.randint(1200, 3500)
    hits = int(base_queries * random.uniform(0.85, 0.96))
    misses = base_queries - hits
    hit_rate = round((hits / base_queries) * 100, 2)
    avg_lat = round(random.uniform(8.5, 24.0), 2)
    
    return {
        'server_id': server_id,
        'server_name': server_name,
        'total_queries': base_queries,
        'qps': round(base_queries / 60.0, 2),
        'cache_hits': hits,
        'cache_misses': misses,
        'cache_hit_rate': hit_rate,
        'prefetch_hits': int(hits * random.uniform(0.1, 0.2)),
        'rrset_cache_num': random.randint(12000, 45000),
        'msg_cache_num': random.randint(20000, 80000),
        'avg_latency': avg_lat,
        'median_latency': round(avg_lat * 0.8, 2),
        'p90_latency': round(avg_lat * 1.8, 2),
        'p95_latency': round(avg_lat * 2.5, 2),
        'p99_latency': round(avg_lat * 4.2, 2),
        'nxdomain_count': random.randint(10, 80),
        'servfail_count': random.randint(0, 5),
        'dnssec_failures': random.randint(0, 3),
        'excessive_txt_queries': random.randint(5, 40),
        'ipv4_queries': int(base_queries * 0.7),
        'ipv6_queries': int(base_queries * 0.3),
        'active_clients': random.randint(40, 180)
    }
