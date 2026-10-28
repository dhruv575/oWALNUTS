"""Pure fixed partitioning; does not load arrays or use randomness."""
MONTHS = (("2026-04",1440),("2026-05",1488),("2026-06",1440))
SHARDS = 12

def assignments(phase, shard):
    if type(shard) is not int or not 0 <= shard < SHARDS:
        raise ValueError("Invalid shard")
    if phase == "candidate":
        items = [(month,tick) for month,n in MONTHS for tick in range(1,n+1)]
    elif phase == "reference":
        items = [(month,index) for month,_ in MONTHS for index in range(8)]
    else:
        raise ValueError("Invalid phase")
    return items[shard::SHARDS]
