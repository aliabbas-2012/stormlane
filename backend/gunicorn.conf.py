"""Gunicorn settings for production (WSGI, threaded workers).

Views are sync DRF; each request fans out to external APIs on its own event loop via
async_to_sync, so threads (not async workers) are the right concurrency model.
"""

import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
worker_class = "gthread"
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
# A cold /api/analyze makes several upstream calls with timeouts and one retry each.
timeout = 60
graceful_timeout = 20
accesslog = "-"
errorlog = "-"
