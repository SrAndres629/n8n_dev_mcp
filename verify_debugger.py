import asyncio
import sys
import os
import json

# Add project root to path
sys.path.append(os.getcwd())

from app.services.debugger import (
    get_execution_history,
    diagnose_execution,
    analyze_execution_failures
)

async def verify_debugger():
    print("🐞 Starting Debugger Skills Verification...")
    
    # 1. Get History
    print("\n1️⃣  Testing get_execution_history...")
    executions = []
    try:
        hist_json = await get_execution_history(limit=5)
        hist = json.loads(hist_json)
        
        if isinstance(hist, dict) and hist.get("status") == "success":
             executions = hist.get("data", [])
             print(f"   ✅ SUCCESS: Found {len(executions)} recent executions.")
        elif isinstance(hist, list):
             executions = hist
             print(f"   ✅ SUCCESS: Found {len(executions)} recent executions.")
        else:
             print(f"   ❌ FAILURE: {hist}")
    except Exception as e:
        print(f"   ❌ FAILURE: {e}")

    # 2. Diagnose specific execution
    if executions:
        target_id = executions[0]["id"]
        print(f"\n2️⃣  Testing diagnose_execution ('{target_id}')...")
        try:
            diag_json = await diagnose_execution(target_id)
            diag = json.loads(diag_json)
            if diag.get("status") == "success":
                print(f"   ✅ SUCCESS: Diagnosis complete (Status: {diag.get('diagnosis', {}).get('status')})")
            else:
                print(f"   ❌ FAILURE: {diag}")
        except Exception as e:
            print(f"   ❌ FAILURE: {e}")
    else:
        print("\n2️⃣  Skipping diagnose_execution (no executions found).")

    # 3. Analyze Failures
    print("\n3️⃣  Testing analyze_execution_failures...")
    try:
        analysis_json = await analyze_execution_failures(limit=5)
        analysis = json.loads(analysis_json)
        if isinstance(analysis, list):
             print(f"   ✅ SUCCESS: Analysis complete.")
             print(f"   - Failed Executions Analyzed: {len(analysis)}")
        elif isinstance(analysis, dict) and analysis.get("status") == "success":
             print(f"   ✅ SUCCESS: Analysis complete.")
             print(f"   - Failed Executions Analyzed: {analysis.get('analysis', {}).get('total_failed_analyzed')}")
        else:
             print(f"   ❌ FAILURE: {analysis}")
    except Exception as e:
        print(f"   ❌ FAILURE: {e}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(verify_debugger())
