import os

# Superset configuration for Predictive Maintenance Mining (Topic 16)
SECRET_KEY = os.environ.get("SUPERSET_SECRET_KEY", "maintenance_predictive_superset_secret_key_2026")
SQLALCHEMY_DATABASE_URI = os.environ.get(
    "SQLALCHEMY_DATABASE_URI",
    "postgresql+psycopg2://postgres:postgres@postgres:5432/superset_metadata"
)

# Application Configuration
APP_NAME = "Predictive Maintenance Superset"
ROW_LIMIT = 100000  # Đảm bảo đọc được toàn bộ 78.000 dòng scores nếu cần
VIZ_ROW_LIMIT = 100000

# Security and Local Deployment
WTF_CSRF_ENABLED = True
WTF_CSRF_EXEMPT_LIST = []
TALISMAN_ENABLED = False  # Tắt HTTPS ép buộc trên môi trường local
ENABLE_PROXY_FIX = True

# Feature Flags
FEATURE_FLAGS = {
    "DASHBOARD_NATIVE_FILTERS": True,
    "DASHBOARD_CROSS_FILTERS": True,
    "DASHBOARD_NATIVE_FILTERS_SET": True,
}

# Cache Configuration
CACHE_CONFIG = {
    "CACHE_TYPE": "SimpleCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
}

