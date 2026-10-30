"""Loaded by Gunicorn from the repository root before master/worker logging.
No deployment, port, worker, timeout or request-handling settings are changed.
"""
from safe_logging import install_safe_logging
install_safe_logging()
