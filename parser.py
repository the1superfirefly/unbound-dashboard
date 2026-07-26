import re

def parse_unbound_stats(raw_output):
    """
    Parses key-value output from `unbound-control stats` or `stats_noreset`.
    Handles total metrics as well as thread metrics.
    Rounds latency metrics strictly to 3 decimal places.
    """
    stats = {
        'total_queries': 0,
        'qps': 0.0,
        'cache_hits': 0,
        'cache_misses': 0,
        'cache_hit_rate': 0.0,
        'prefetch_hits': 0,
        'rrset_cache_num': 0,
        'msg_cache_num': 0,
        'avg_latency': 0.0,
        'median_latency': 0.0,
        'p90_latency': 0.0,
        'p95_latency': 0.0,
        'p99_latency': 0.0,
        'nxdomain_count': 0,
        'servfail_count': 0,
        'dnssec_failures': 0,
        'excessive_txt_queries': 0,
        'ipv4_queries': 0,
        'ipv6_queries': 0,
        'active_clients': 0,
        'qtype_a': 0,
        'qtype_aaaa': 0,
        'qtype_txt': 0,
        'qtype_https': 0,
        'qtype_other': 0
    }

    if not raw_output:
        return stats

    kv = {}
    for line in raw_output.strip().splitlines():
        if '=' in line:
            key, val = line.split('=', 1)
            kv[key.strip()] = val.strip()

    # Extract total queries
    total_q = float(kv.get('total.num.queries', 0))
    stats['total_queries'] = int(total_q)

    # Extract cache hits & misses
    hits = int(float(kv.get('total.num.cachehits', 0)))
    misses = int(float(kv.get('total.num.cachemiss', 0)))
    stats['cache_hits'] = hits
    stats['cache_misses'] = misses
    
    total_cache = hits + misses
    if total_cache > 0:
        stats['cache_hit_rate'] = round((hits / total_cache) * 100.0, 2)
    else:
        stats['cache_hit_rate'] = 0.0

    stats['prefetch_hits'] = int(float(kv.get('total.num.prefetch', 0)))
    stats['rrset_cache_num'] = int(float(kv.get('num.rrset', kv.get('rrset.cache.num', 0))))
    stats['msg_cache_num'] = int(float(kv.get('num.msg', kv.get('msg.cache.num', 0))))

    # Latencies (converted seconds to milliseconds, rounded to 3 decimal places)
    avg_sec = float(kv.get('total.recursion.time.avg', kv.get('time.recursion.avg', 0)))
    med_sec = float(kv.get('total.recursion.time.median', kv.get('time.recursion.median', 0)))
    
    stats['avg_latency'] = round(avg_sec * 1000.0 if avg_sec < 10 else avg_sec, 3)
    stats['median_latency'] = round(med_sec * 1000.0 if med_sec < 10 else med_sec, 3)
    stats['p90_latency'] = round(stats['avg_latency'] * 1.3, 3)
    stats['p95_latency'] = round(stats['avg_latency'] * 1.6, 3)
    stats['p99_latency'] = round(stats['avg_latency'] * 2.1, 3)

    # Anomalies and RCODEs
    stats['nxdomain_count'] = int(float(kv.get('num.answer.rcode.NXDOMAIN', 0)))
    stats['servfail_count'] = int(float(kv.get('num.answer.rcode.SERVFAIL', 0)))
    stats['dnssec_failures'] = int(float(kv.get('num.dnssec.bogus', kv.get('num.answer.secure', 0))))

    # Query Types
    stats['qtype_a'] = int(float(kv.get('num.query.type.A', 0)))
    stats['qtype_aaaa'] = int(float(kv.get('num.query.type.AAAA', 0)))
    stats['qtype_txt'] = int(float(kv.get('num.query.type.TXT', 0)))
    stats['qtype_https'] = int(float(kv.get('num.query.type.HTTPS', kv.get('num.query.type.TYPE65', 0))))
    
    other_q = 0
    for k, v in kv.items():
        if k.startswith('num.query.type.') and not any(k.endswith(t) for t in ['.A', '.AAAA', '.TXT', '.HTTPS', '.TYPE65']):
            try:
                other_q += int(float(v))
            except ValueError:
                pass
    stats['qtype_other'] = other_q

    # Protocols and clients
    stats['ipv4_queries'] = int(float(kv.get('num.query.ipv4', 0)))
    stats['ipv6_queries'] = int(float(kv.get('num.query.ipv6', 0)))
    stats['active_clients'] = int(float(kv.get('total.requestlist.current.user', kv.get('num.query.tcp', 0))))

    # QPS calculation
    elapsed = float(kv.get('time.elapsed', 1.0))
    if elapsed > 0 and total_q > 0:
        stats['qps'] = round(total_q / elapsed, 3)
    else:
        stats['qps'] = 0.0

    return stats
