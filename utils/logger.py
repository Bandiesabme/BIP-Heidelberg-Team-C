"""
utils/logger.py — Shared logging utilities.

Provides a configured logger for debugging the 30Hz control loop.
Use file-based logging (RotatingFileHandler) instead of print()
for post-mortem analysis.
"""

# TODO: Implement a shared logging setup:
#   1. Create a get_logger(name: str) -> logging.Logger function
#   2. Configure RotatingFileHandler (e.g., maxBytes=5MB, backupCount=3)
#   3. Format: "%(asctime)s | %(processName)s | %(levelname)s | %(message)s"
#   4. Optionally add a per-tick log function:
#      def log_tick(logger, state: SensorState, action: ActionCommand):
#          logger.debug(f"state={state} -> action={action}")
