import asyncio
import sys
import os
import json

# Add project root to path
sys.path.append(os.getcwd())

from app.services.manager import list_all_workflows
from app.services.credentials import list_credentials
from app.core.config import settings

async def verify_services():
    print("🚀 Starting Deep Service Verification...")
    
    print(f"   - Settings API URL: {settings.api_url}")
    
    # Test Client /users connectivity (Known Good from audit)
    print("\n0️⃣  Testing Client connection to /users...")
    try:
        from app.core.client import get_client
        client = get_client()
        # manual request using the client wrapper
        users = await client.get("/users")
        print(f"   ✅ SUCCESS: Retrieved users via Client wrapper.")
    except Exception as e:
        print(f"   ❌ FAILURE: Client wrapper failed on /users: {e}")

    # Test Workflow Service
    print("\n1️⃣  Testing Workflow Service (list_all_workflows)...")
    try:
        workflows_json = await list_all_workflows()
        
        # Parse JSON to check for error
        try:
             workflows = json.loads(workflows_json)
             if isinstance(workflows, dict) and workflows.get("status") == "error":
                 print(f"   ❌ API ERROR: {workflows}")
             elif isinstance(workflows, list):
                print(f"   ✅ SUCCESS: Retrieved {len(workflows)} workflows.")
             else:
                print(f"   ℹ️  Response: {str(workflows)[:100]}")
        except:
             print(f"   RAW: {workflows_json[:100]}")

    except Exception as e:
        print(f"   ❌ FAILURE: Workflow service exception: {e}")

    # Test Credential Service
    print("\n2️⃣  Testing Credential Service (list_credentials)...")
    try:
        creds_json = await list_credentials()
        creds = json.loads(creds_json)
        
        # Check for standard n8n response wrapper "data" or direct list
        data = creds.get('data', creds) if isinstance(creds, dict) else creds
        
        if isinstance(data, list):
            print(f"   ✅ SUCCESS: Retrieved {len(data)} credentials.")
        else:
            print(f"   ⚠️  WARNING: Response format unexpected: {str(creds)[:100]}")
            
    except Exception as e:
        print(f"   ❌ FAILURE: Credential service crashed: {e}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(verify_services())
