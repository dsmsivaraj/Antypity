"""Utility to aggregate & print current in-memory retrieval counters and optionally persist a snapshot to DB."""
from backend.metrics import current_counters

if __name__ == '__main__':
    print('Current counters:', current_counters())
