import asyncio
import sys
import os
import json

# Add project root to path
sys.path.append(os.getcwd())

from app.services.architect import (
    deploy_workflow,
    clone_workflow,
    read_workflow_structure
)
from app.services.manager import delete_workflow

async def verify_architect():
    print("🏗️  Starting Architect Skills Verification...")
    
    test_wf_name = "MCP_VERIFICATION_TEST_WORKFLOW"
    clone_wf_name = "MCP_VERIFICATION_CLONE_TEST"
    
    # 1. Deploy (Create) Workflow
    print(f"\n1️⃣  Testing deploy_workflow ('{test_wf_name}')...")
    nodes = [
        {
            "parameters": {},
            "name": "Start",
            "type": "n8n-nodes-base.start",
            "typeVersion": 1,
            "position": [250, 300]
        }
    ]
    connections = {}
    
    wf_id = None
    try:
        # Note: arguments must be serialized JSON strings if passed from tool env, 
        # but the python function accepts List/Dict due to our internal parser.
        # We'll pass objects to be safe using the internal function directly.
        result_json = await deploy_workflow(
            name=test_wf_name, 
            nodes=nodes, 
            connections=connections,
            activate=False
        )
        result = json.loads(result_json)
        
        if result.get("status") == "success":
            wf_id = result.get("id")
            print(f"   ✅ SUCCESS: Created workflow ID: {wf_id}")
        else:
            print(f"   ❌ FAILURE: {result}")
            return
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"   ❌ FAILURE: {e}")
        return

    if not wf_id:
        return

    # 2. Read Workflow Structure
    print(f"\n2️⃣  Testing read_workflow_structure ('{wf_id}')...")
    try:
        structure_json = await read_workflow_structure(wf_id)
        structure = json.loads(structure_json)
        if structure.get("name") == test_wf_name:
            print(f"   ✅ SUCCESS: Verified workflow structure reading.")
        else:
            print(f"   ⚠️  WARNING: Name mismatch or error: {structure.get('name')}")
    except Exception as e:
        print(f"   ❌ FAILURE: {e}")

    # 3. Clone Workflow
    print(f"\n3️⃣  Testing clone_workflow ('{clone_wf_name}')...")
    clone_id = None
    try:
        clone_json = await clone_workflow(source_id=wf_id, new_name=clone_wf_name)
        clone_res = json.loads(clone_json)
        if clone_res.get("status") == "success":
             clone_id = clone_res.get("id")
             print(f"   ✅ SUCCESS: Cloned workflow ID: {clone_id}")
        else:
             print(f"   ❌ FAILURE: {clone_res}")
    except Exception as e:
        print(f"   ❌ FAILURE: {e}")

    # 4. Cleanup (Delete both)
    print(f"\n4️⃣  Cleanup: Deleting test workflows...")
    try:
        await delete_workflow(wf_id)
        print(f"   ✅ Deleted original: {wf_id}")
    except Exception as e:
        print(f"   ❌ Failed to delete original: {e}")
        
    if clone_id:
        try:
            await delete_workflow(clone_id)
            print(f"   ✅ Deleted clone: {clone_id}")
        except Exception as e:
            print(f"   ❌ Failed to delete clone: {e}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(verify_architect())
