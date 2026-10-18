import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8811')}"

# ---------------------------------------------------------------------------
# workers MUST stay at 1.
#
# The selector config lives in this process's memory. With two workers you get
# two independent copies: a PATCH lands in one, and subsequent page loads are
# balanced across both, so the shop flips between old and new markup at random.
# That failure is intermittent, invisible in the logs, and would be discovered
# on stage.
#
# Concurrency comes from threads instead, which share the one config. The store
# guards mutations with a lock, and each request renders from a request-local
# snapshot. Fixed lab profiles do not use the mutable legacy store.
# ---------------------------------------------------------------------------
workers = 1
worker_class = "gthread"
threads = int(os.environ.get("THREADS", "8"))

accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")
forwarded_allow_ips = "*"  # behind Caddy; trust its X-Forwarded-* headers
graceful_timeout = 10
timeout = 30
