#!/bin/bash
# startup.sh — catch and log any startup errors before uvicorn
set -e

echo "=== Enterprise GenAI Content Studio startup ==="
echo "PORT=${PORT:-8000}"
echo "CLOUD_PROVIDER=${CLOUD_PROVIDER:-not set}"
echo "AZURE_AI_ENDPOINT=${AZURE_AI_ENDPOINT:-not set}"

# Validate Python can import the app
python -c "
import sys
import traceback
print('[startup] Testing imports...')
try:
    from src.config import get_settings
    s = get_settings()
    print(f'[startup] Settings OK: cloud={s.cloud_provider}')
except Exception as e:
    print(f'[startup] SETTINGS ERROR: {e}', file=sys.stderr)
    traceback.print_exc()
    # Don't exit — uvicorn will also fail and show the error

try:
    from src.main import app
    print('[startup] App import OK')
except Exception as e:
    print(f'[startup] APP IMPORT ERROR: {e}', file=sys.stderr)
    traceback.print_exc()
    sys.exit(1)

print('[startup] All imports successful, starting uvicorn...')
"

PORT="${PORT:-8000}"
exec uvicorn src.main:app --host 0.0.0.0 --port "$PORT" --workers 1 --log-level info
