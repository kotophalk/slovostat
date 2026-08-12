import os

RATE_LIMIT_PER_DAY = int(os.environ.get("SLOVOSTAT_RATE_LIMIT", "25"))
REQUEST_TIMEOUT = int(os.environ.get("SLOVOSTAT_TIMEOUT", "10"))
DATABASE_PATH = os.environ.get("SLOVOSTAT_DB_PATH", "slovostat.db")
