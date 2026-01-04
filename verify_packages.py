import asyncio
import sys
import os
import json

# Add project root to path
sys.path.append(os.getcwd())

from app.services.packages import (
    get_n8n_info,
    list_installed_nodes
)

async def verify_packages():
    print("📦 Starting Package Management Verification...")
    
    # 1. Get n8n Info
    print("\n1️⃣  Testing get_n8n_info...")
    try:
        info_json = await get_n8n_info()
        print(f"   ✅ SUCCESS: {info_json}")
    except Exception as e:
        print(f"   ❌ FAILURE: {e}")

    # 2. List Installed Nodes
    print("\n2️⃣  Testing list_installed_nodes...")
    try:
        nodes_json = await list_installed_nodes()
        nodes = json.loads(nodes_json)
        print(f"   ✅ SUCCESS: Found {len(nodes.get('packages', []))} custom nodes.")
    except Exception as e:
        print(f"   ❌ FAILURE: {e}")
        
    # Note: skipped install/uninstall to avoid modifying user environment unnecessarily
    # unless user explicitly requests "test install".

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(verify_packages())
