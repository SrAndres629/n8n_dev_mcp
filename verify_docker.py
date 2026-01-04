import asyncio
import sys
import os
import json

# Add project root to path
sys.path.append(os.getcwd())

from app.services.docker import (
    list_docker_containers,
    get_container_inspect,
    get_container_logs,
    get_container_stats,
    analyze_all_container_errors
)

async def verify_docker():
    # Redirect stdout/stderr to file
    log_file = open("docker_verify.log", "w", encoding="utf-8")
    sys.stdout = log_file
    sys.stderr = log_file

    print("🐳 Starting Docker Skills Verification...")
    print(f"   - CWD: {os.getcwd()}")
    print(f"   - Python: {sys.version}")
    
    try:
        import docker
        print(f"   - Docker SDK Version: {docker.__version__}")
        client = docker.from_env()
        print(f"   - Docker Ping: {client.ping()}")
    except Exception as e:
        print(f"   ❌ Docker Import/Ping Check Failed: {e}")

    # 1. List Containers
    print("\n1️⃣  Testing list_docker_containers...")
    try:
        result_json = await list_docker_containers(all_containers=True)
        result = json.loads(result_json)
        
        if result.get("status") == "success":
            count = result.get("count", 0)
            print(f"   ✅ SUCCESS: Found {count} containers.")
            containers = result.get("containers", [])
        else:
            print(f"   ❌ FAILURE: {result}")
            return
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"   ❌ CRITICAL FAILURE: {e}")
        return

    containers = [] # Ensure defined
    try:
        # Re-parse if needed or just use from above if success
        if result.get("status") == "success":
             containers = result.get("containers", [])
    except:
        pass
        print("   ⚠️  No containers found. Cannot proceed with specific container tests.")
        return

    # Pick the first running container, or just the first one
    target_container = next((c for c in containers if c["status"] == "running"), containers[0])
    target_name = target_container["name"]
    print(f"   ℹ️  Targeting container: {target_name} ({target_container['status']})")

    # 2. Inspect Container
    print(f"\n2️⃣  Testing get_container_inspect('{target_name}')...")
    try:
        inspect_json = await get_container_inspect(target_name)
        inspect = json.loads(inspect_json)
        if inspect.get("status") == "success":
             print(f"   ✅ SUCCESS: Retrieved inspection data.")
        else:
             print(f"   ❌ FAILURE: {inspect}")
    except Exception as e:
        print(f"   ❌ FAILURE: {e}")

    # 3. Get Logs
    print(f"\n3️⃣  Testing get_container_logs('{target_name}')...")
    try:
        logs_json = await get_container_logs(target_name, tail=10)
        logs = json.loads(logs_json)
        if logs.get("status") == "success":
            print(f"   ✅ SUCCESS: Retrieved logs.")
        else:
            print(f"   ❌ FAILURE: {logs}")
    except Exception as e:
        print(f"   ❌ FAILURE: {e}")

    # 4. Get Stats
    print(f"\n4️⃣  Testing get_container_stats('{target_name}')...")
    try:
        stats_json = await get_container_stats(target_name)
        stats = json.loads(stats_json)
        if stats.get("status") == "success":
            print(f"   ✅ SUCCESS: Retrieved stats (CPU: {stats['cpu']['percent']}%, MEM: {stats['memory']['percent']}%).")
        elif stats.get("status") == "warning":
             print(f"   ⚠️  WARNING: {stats.get('message')}")
        else:
            print(f"   ❌ FAILURE: {stats}")
    except Exception as e:
        print(f"   ❌ FAILURE: {e}")
        
    # 5. Analyze All Errors
    print(f"\n5️⃣  Testing analyze_all_container_errors...")
    try:
        analysis_json = await analyze_all_container_errors()
        analysis = json.loads(analysis_json)
        if analysis.get("status") == "success":
            summary = analysis.get("summary", {})
            print(f"   ✅ SUCCESS: Analyzed {summary.get('total_containers')} containers.")
            print(f"   - Issues found: {summary.get('total_issues')}")
        else:
            print(f"   ❌ FAILURE: {analysis}")
    except Exception as e:
        print(f"   ❌ FAILURE: {e}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(verify_docker())
