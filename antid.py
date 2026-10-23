import asyncio
import random
import time

CFG = {
    'batch_min': 1.4,
    'batch_max': 4.2,
    'burst_every': 4,
    'burst_min': 5.5,
    'burst_max': 12.0,
    'jitter_pct': 0.28,
    'typo_chance': 0.0,
    'cmd_min': 0.12,
    'cmd_max': 0.48,
    'react_min': 0.25,
    'react_max': 1.1,
    'mass_min': 1.0,
    'mass_max': 2.8,
}

_last_action = 0.0
_action_count = 0

def jitter(base: float, pct: float | None = None) -> float:
    p = pct if pct is not None else CFG['jitter_pct']
    return max(0.05, base * (1 + random.uniform(-p, p)))

async def delay(min_s: float | None = None, max_s: float | None = None):
    lo = min_s if min_s is not None else CFG['batch_min']
    hi = max_s if max_s is not None else CFG['batch_max']
    if hi < lo:
        hi = lo
    await asyncio.sleep(random.uniform(lo, hi))

async def batch_delay(n: int = 1):
    global _action_count
    _action_count = n
    if n > 0 and n % CFG['burst_every'] == 0:
        await asyncio.sleep(random.uniform(CFG['burst_min'], CFG['burst_max']))
    else:
        await asyncio.sleep(random.uniform(CFG['batch_min'], CFG['batch_max']))

def shuffled(seq):
    lst = list(seq)
    random.shuffle(lst)
    return lst

async def on_rate_limit(retry_after: float):
    wait = float(retry_after) + random.uniform(1.2, 4.0)
    wait = min(max(wait, 1.0), 90.0)
    print(f'[antid] rate limited - waiting {wait:.1f}s')
    await asyncio.sleep(wait)

def rand_interval(base_minutes: float) -> float:
    base_s = base_minutes * 60
    return jitter(base_s, CFG['jitter_pct'])

async def burst_protect(n: int, every: int = 4, lo: float = 0.4, hi: float = 1.2):
    if n > 0 and every > 0 and n % every == 0:
        await asyncio.sleep(random.uniform(lo * 4, hi * 5))
    else:
        await asyncio.sleep(random.uniform(lo, hi))

def human_pause(kind: str = 'chat') -> float:
    table = {
        'chat': (CFG['batch_min'], CFG['batch_max']),
        'cmd': (CFG['cmd_min'], CFG['cmd_max']),
        'mass': (CFG['mass_min'], CFG['mass_max']),
        'react': (CFG['react_min'], CFG['react_max']),
        'join': (2.0, 6.0),
        'report': (3.0, 8.0),
    }
    lo, hi = table.get(kind, (0.3, 1.2))
    return random.uniform(lo, hi)

async def pace(kind: str = 'chat'):
    global _last_action
    now = time.monotonic()
    need = human_pause(kind)
    elapsed = now - _last_action
    if elapsed < need:
        await asyncio.sleep(need - elapsed)
    _last_action = time.monotonic()

async def soft_429(resp=None, fallback: float = 2.0):
    wait = fallback
    try:
        if resp is not None:
            h = getattr(resp, 'headers', None) or {}
            if h.get('Retry-After'):
                wait = float(h.get('Retry-After'))
            elif getattr(resp, 'status', None) == 429:
                try:
                    data = await resp.json(content_type=None)
                    wait = float(data.get('retry_after', wait))
                except Exception:
                    wait = max(fallback, 3.0)
    except Exception:
        pass
    await on_rate_limit(wait)
