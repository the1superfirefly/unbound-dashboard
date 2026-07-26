def parse_unbound_stats(raw_stats_str):
    """
    Parses key=value output from `unbound-control stats_noreset`.
    """
    stats = {}
    if not raw_stats_str:
        return None
        
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
    cache_hit_rate = round((cache_hits / total_cache * 100), 2) if total_cache > 0 else 0.0

    return {
        'total_queries': num_queries,
        'qps': stats.get('total.num.queries.ip', round(num_queries / 60.0, 2)),
        'cache_hits': cache_hits,
        'cache_misses': cache_miss,
        'cache_hit_rate': cache_hit_rate,
        'prefetch_hits': stats.get('total.num.prefetch', 0),
        'rrset_cache_num': stats.get('msg.cache.count', 0),
        'msg_cache_num': stats.get('rrset.cache.count', 0),
        'avg_latency': stats.get('total.recursion.time.avg', 0.0),
        'median_latency': stats.get('total.recursion.time.median', 0.0),
        'p90_latency': 0.0,
        'p95_latency': 0.0,
        'p99_latency': 0.0,
        'nxdomain_count': stats.get('num.answer.rcode.NXDOMAIN', 0),
        'servfail_count': stats.get('num.answer.rcode.SERVFAIL', 0),
        'dnssec_failures': stats.get('num.dnssec.bogus', 0),
        'excessive_txt_queries': stats.get('num.query.type.TXT', 0),
        'ipv4_queries': stats.get('num.query.ipv4', 0),
        'ipv6_queries': stats.get('num.query.ipv6', 0),
        'active_clients': stats.get('total.num.queries.ip', 0)
    }
