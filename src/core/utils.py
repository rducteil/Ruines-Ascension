def clamp(n, lo, hi):
    if n < lo:
        return lo
    elif n > hi:
        return hi
    else:
        return n
    
def normalize(d: dict[int, float]) -> dict[int, float]:
    s = sum(d.values()) or 1.0
    return {k: v / s for k, v in d.items()}