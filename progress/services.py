"""
Business-logic services for the progress app.
Unlock rules, anti-cheat heartbeat math, enrollment helpers.

Anti-cheat rule (from project spec):
    server adds min(reported_forward_delta,
                    real_elapsed_seconds_since_last_heartbeat + 2)
    to watched_seconds on each heartbeat.
"""
