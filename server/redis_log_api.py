#!/usr/bin/env python3
"""
Redis-based log API - Ultra-fast log queries using Redis cache.
Replaces file-based log parsing with Redis lookups.
"""

import os
import redis
import json
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from typing import Dict, List, Optional
import hashlib
import re

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), '..', 'templates'))

# Configure Flask for minimal memory usage
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
app.config['JSON_SORT_KEYS'] = False
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 300

class RedisLogAPI:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=os.environ.get('REDIS_HOST', '127.0.0.1'),
            port=int(os.environ.get('REDIS_PORT', 6379)),
            db=int(os.environ.get('REDIS_DB', 0)),
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        
        # Query cache settings
        self.query_cache_ttl = 300  # 5 minutes
        self.max_results = 500
        
        print("✅ Redis Log API initialized")

    def get_logs(self, host: str, app: str = None, component: str = None,
                 level: str = None, refresh_id: str = None, step: str = None,
                 start_time: datetime = None, end_time: datetime = None,
                 search_query: str = None, limit: int = 100, offset: int = 0) -> Dict:
        """Get logs from Redis with advanced filtering."""
        
        # Build Redis key pattern
        if app and component:
            base_key = f"logs:{host}:{app}:{component}"
        elif app:
            base_key = f"logs:{host}:{app}:*"
        else:
            base_key = f"logs:{host}:*"
        
        # Apply filters to build specific key
        query_key = base_key
        if level:
            query_key += f":level:{level}"
        elif refresh_id:
            query_key += f":refresh:{refresh_id}"
        elif step:
            query_key += f":step:{step}"
        
        # Calculate time range scores
        start_score = 0
        end_score = '+inf'
        
        if start_time:
            start_score = int(start_time.timestamp())
        if end_time:
            end_score = int(end_time.timestamp())
        
        # Check query cache first
        cache_key = self._generate_cache_key(query_key, start_score, end_score, limit, offset)
        cached_result = self.redis_client.get(f"cache:{cache_key}")
        if cached_result:
            return json.loads(cached_result)
        
        try:
            # Get log entry keys from sorted set
            if '*' in query_key:
                # Handle wildcard queries
                log_keys = self._get_wildcard_logs(base_key, start_score, end_score, limit + offset)
            else:
                # Direct key query
                log_keys = self.redis_client.zrevrangebyscore(
                    query_key, end_score, start_score,
                    start=offset, num=limit
                )
            
            # Fetch log entries
            logs = []
            for key in log_keys[offset:offset + limit]:
                log_data = self.redis_client.hgetall(key)
                if log_data:
                    # Apply search filter if specified
                    if search_query and search_query.lower() not in log_data.get('message', '').lower():
                        continue
                    logs.append(log_data)
            
            result = {
                'logs': logs,
                'total': len(log_keys),
                'limit': limit,
                'offset': offset,
                'query_time_ms': 0,  # Redis queries are sub-millisecond
                'source': 'redis_cache'
            }
            
            # Cache the result
            self.redis_client.setex(f"cache:{cache_key}", self.query_cache_ttl, json.dumps(result))
            
            return result
            
        except Exception as e:
            print(f"Redis query error: {e}")
            return {'logs': [], 'total': 0, 'error': str(e)}

    def _get_wildcard_logs(self, pattern: str, start_score, end_score, limit: int) -> List[str]:
        """Handle wildcard queries by scanning multiple keys."""
        all_logs = []

        # Get all matching keys
        for key in self.redis_client.scan_iter(match=pattern):
            if ':level:' in key or ':refresh:' in key or ':step:' in key:
                continue  # Skip filter keys

            # Get logs from this sorted set with scores
            key_logs_with_scores = self.redis_client.zrevrangebyscore(
                key, end_score, start_score, start=0, num=limit, withscores=True
            )

            # Add to our collection with the actual scores from this key
            for log_key, score in key_logs_with_scores:
                all_logs.append((log_key, score))

        # Sort by timestamp (newest first) and limit
        all_logs.sort(key=lambda x: x[1], reverse=True)
        return [log_key for log_key, score in all_logs[:limit]]

    def _generate_cache_key(self, query_key: str, start_score, end_score, limit: int, offset: int) -> str:
        """Generate cache key for query."""
        content = f"{query_key}:{start_score}:{end_score}:{limit}:{offset}"
        return hashlib.md5(content.encode()).hexdigest()

    def get_stats(self, host: str, app: str = None) -> Dict:
        """Get statistics from Redis."""
        if app:
            stats_key = f"logs:stats:{host}:{app}"
        else:
            stats_key = f"logs:stats:{host}:*"
        
        if '*' in stats_key:
            # Aggregate stats from multiple apps
            total_stats = {}
            for key in self.redis_client.scan_iter(match=stats_key):
                app_stats = self.redis_client.hgetall(key)
                for stat_key, value in app_stats.items():
                    total_stats[stat_key] = total_stats.get(stat_key, 0) + int(value)
            return total_stats
        else:
            return self.redis_client.hgetall(stats_key)

    def search_logs(self, host: str, query: str, limit: int = 100) -> Dict:
        """Full-text search across logs."""
        # For now, implement basic search
        # In production, consider Redis Search module for advanced full-text search
        
        search_results = []
        pattern = f"logs:{host}:*"
        
        for key in self.redis_client.scan_iter(match=pattern):
            if ':level:' in key or ':refresh:' in key or ':step:' in key:
                continue
                
            # Get recent logs from this key
            recent_logs = self.redis_client.zrevrange(key, 0, 100)
            
            for log_key in recent_logs:
                log_data = self.redis_client.hgetall(log_key)
                if log_data and query.lower() in log_data.get('message', '').lower():
                    search_results.append(log_data)
                    
                if len(search_results) >= limit:
                    break
                    
            if len(search_results) >= limit:
                break
        
        return {
            'logs': search_results[:limit],
            'total': len(search_results),
            'query': query,
            'source': 'redis_search'
        }

# Initialize Redis API
redis_api = RedisLogAPI()

@app.route('/')
def dashboard():
    """Enhanced log viewer dashboard."""
    from flask import render_template
    return render_template('enhanced_dashboard.html')

@app.route('/health')
def health():
    """Health check endpoint with Redis statistics."""
    try:
        redis_api.redis_client.ping()

        # Get Redis memory info
        memory_info = redis_api.redis_client.info('memory')

        # Count total log keys
        log_keys = len(list(redis_api.redis_client.scan_iter(match='logs:*')))

        return jsonify({
            'status': 'healthy',
            'redis_connected': True,
            'redis_memory_used': memory_info.get('used_memory_human', 'unknown'),
            'total_log_keys': log_keys,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'redis_connected': False,
            'error': str(e)
        }), 500

@app.route('/logger/redis/<host>')
def get_host_logs_redis(host):
    """Get logs for host using Redis backend."""
    # Parse query parameters
    app = request.args.get('app', 'all')
    component = request.args.get('component')
    level = request.args.get('level')
    refresh_id = request.args.get('refresh_id')
    step = request.args.get('step')
    search = request.args.get('search')
    limit = min(int(request.args.get('limit', 100)), 500)
    offset = int(request.args.get('offset', 0))
    
    # Parse time filters
    start_time = None
    end_time = None
    time_filter = request.args.get('time')
    if time_filter:
        start_time, end_time = parse_time_filter(time_filter)
    
    result = redis_api.get_logs(
        host=host,
        app=app if app != 'all' else None,
        component=component,
        level=level,
        refresh_id=refresh_id,
        step=step,
        start_time=start_time,
        end_time=end_time,
        search_query=search,
        limit=limit,
        offset=offset
    )
    
    return jsonify(result)

@app.route('/logger/search/redis/<host>')
def search_host_logs_redis(host):
    """Search logs for host using Redis backend."""
    query = request.args.get('search', '')
    limit = min(int(request.args.get('limit', 100)), 500)
    
    if not query:
        return jsonify({'error': 'Search query required'}), 400
    
    result = redis_api.search_logs(host, query, limit)
    return jsonify(result)

@app.route('/logger/stats/redis/<host>')
def get_host_stats_redis(host):
    """Get statistics for host using Redis backend."""
    app = request.args.get('app')
    result = redis_api.get_stats(host, app)
    return jsonify(result)

def parse_time_filter(time_str):
    """Parse time filter string - simplified version."""
    if not time_str:
        return None, None
    
    now = datetime.now()
    
    if 'last hour' in time_str.lower():
        return now - timedelta(hours=1), now
    elif 'today' in time_str.lower():
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now
    elif 'yesterday' in time_str.lower():
        yesterday = now - timedelta(days=1)
        start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start, end
    
    return None, None

if __name__ == '__main__':
    # Get configuration from environment
    host = os.getenv('API_HOST', '0.0.0.0')
    port = int(os.getenv('API_PORT', '8082'))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

    print(f"🚀 Starting Redis Log API on {host}:{port}")
    app.run(host=host, port=port, debug=debug)
