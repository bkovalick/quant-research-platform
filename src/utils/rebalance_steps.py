# (market_frequency, rebalance_frequency) -> steps between rebalances
FREQ_TO_STEPS = {
    # daily market data
    ("d", "daily"):     1,
    ("d", "weekly"):    5,
    ("d", "monthly"):   21,
    ("d", "quarterly"): 63,
    ("d", "yearly"):    252,
    # weekly market data (daily rebal = every step, same as weekly)
    ("w", "daily"):     1,
    ("w", "weekly"):    1,
    ("w", "monthly"):   4,
    ("w", "quarterly"): 13,
    ("w", "yearly"):    52,
    # monthly market data (daily/weekly rebal = every step, same as monthly)
    ("m", "daily"):     1,
    ("m", "weekly"):    1,
    ("m", "monthly"):   1,
    ("m", "quarterly"): 3,
    ("m", "yearly"):    12,
}