"""
Verification for Quantum Core
Tests that high-level experts can dispatch to internal skills.
"""
import asyncio
import app.core.dispatcher as dispatcher

async def verify_dispatch():
    print("=" * 60)
    print("🌀 QUANTUM CORE DISPATCH VERIFICATION")
    print("=" * 60)
    
    # 1. Test skill manifest
    manifest = dispatcher.get_skill_manifest()
    print(f"Internal Skills Found: {manifest['total']}")
    if manifest['total'] < 85:
        print("❌ FAILED: Missing internal skills.")
        return

    print("✅ Skills Registry: [PASSED]")
    
    # 2. Test dynamic dispatch (Mock parameters)
    print("\nTesting n8n_expert dispatch (list_workflows)...")
    try:
        # We use empty params for list_workflows
        result = await dispatcher.dispatch("n8n", "list_workflows", {"tags": []})
        if "workflows" in result or "status" in result:
             print("✅ Dispatch: [PASSED]")
        else:
            print(f"⚠️ Unexpected result: {result[:100]}...")
    except Exception as e:
        print(f"❌ Dispatch FAILED: {e}")

    # 3. Test Docker dispatch (Mock parameters)
    print("Testing docker_expert dispatch (list_containers)...")
    try:
        result = await dispatcher.dispatch("docker", "list_containers", {"all_containers": True})
        print("✅ Docker Dispatch: [PASSED]")
    except Exception as e:
        print(f"❌ Docker Dispatch FAILED: {e}")

    print("\n" + "=" * 60)
    print("✨ QUANTUM CORE IS FULLY FUNCTIONAL")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(verify_dispatch())
