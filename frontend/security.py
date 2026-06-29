from django.core.cache import cache


def request_is_rate_limited(request, action, limit=5, window_seconds=900):
    address = request.META.get("REMOTE_ADDR", "unknown")
    cache_key = f"fuelops-rate:{action}:{address}"
    attempts = cache.get(cache_key)
    if attempts is None:
        cache.set(cache_key, 1, timeout=window_seconds)
        return False

    try:
        attempts = cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1, timeout=window_seconds)
        return False
    return attempts > limit
