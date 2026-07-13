import os

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
threads = int(os.getenv("WEB_THREADS", "4"))
timeout = int(os.getenv("WEB_TIMEOUT", "30"))
accesslog = "-"
errorlog = "-"
capture_output = True
