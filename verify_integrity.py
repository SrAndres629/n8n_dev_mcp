
import sys
import os

print("Running integrity check...")
try:
    print("Checking app.services.docker...")
    import app.services.docker
    print("✅ app.services.docker imported successfully")
except Exception as e:
    print(f"❌ Error importing app.services.docker: {e}")
    sys.exit(1)

try:
    print("Checking app.main...")
    import app.main
    print("✅ app.main imported successfully")
except Exception as e:
    print(f"❌ Error importing app.main: {e}")
    sys.exit(1)

print("✅ All modules verified integrity.")
