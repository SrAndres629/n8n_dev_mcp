
import asyncio
import json
import os
from app.services.docker import (
    list_container_files,
    read_container_file,
    run_container_command,
    prune_docker_images,
    check_container_connection,
    audit_image_freshness,
    check_container_connection
)

# Mocking docker where needed or expecting a real environment.
# Assuming we can find at least one running container to test against.

async def main():
    log_file = "verify_god_mode.log"
    with open(log_file, "w", encoding="utf-8") as f:
        def log(msg):
            print(msg)
            f.write(str(msg) + "\n")

        log("🚀 Starting God Mode Verification...")
        
        # 1. List containers to find a target
        from app.services.docker import list_docker_containers
        containers_json = await list_docker_containers(filter_status="running")
        containers = json.loads(containers_json).get("containers", [])
        
        if not containers:
            log("⚠️ No running containers found. Skipping interactive tests.")
            return

        target_container = containers[0]["name"]
        log(f"📦 Selected target container: {target_container}")
        
        # 2. Test File Listing
        log(f"\n[Test 1] Listing files in /etc of {target_container}...")
        files_res = await list_container_files(target_container, "/etc")
        log(files_res[:200] + "..." if len(files_res) > 200 else files_res)
        
        # 3. Test Command Execution
        log("\n[Test 2] Running 'whoami'...")
        cmd_res = await run_container_command(target_container, "whoami")
        log(cmd_res)
        
        # 4. Test Connectivity (Loopback check)
        log("\n[Test 3] Checking connectivity to google.com:80...")
        conn_res = await check_container_connection(target_container, "google.com", 80)
        log(conn_res[:500] + "..." if len(conn_res) > 500 else conn_res)
        
        # 5. Test Image Freshness
        image_name = containers[0]["image"]
        log(f"\n[Test 4] Auditing image freshness for {image_name}...")
        try:
            fresh_res = await audit_image_freshness(image_name)
            log(fresh_res)
        except Exception as e:
            log(f"Audit failed: {e}")

        # 6. Test Prune (Dry Run)
        log("\n[Test 5] Pruning images (dry-run)...")
        prune_res = await prune_docker_images(dry_run=True)
        log(prune_res)

        # 7. Test Security Scan
        log(f"\n[Test 6] Security Audit for {target_container}...")
        from app.services.docker import scan_container_security, recommend_resource_limits, check_port_availability
        
        sec_res = await scan_container_security(target_container)
        log(sec_res)

        # 8. Test Resource Limits
        log(f"\n[Test 7] Resource Recommendations for {target_container}...")
        res_limits = await recommend_resource_limits(target_container)
        log(res_limits)

        # 9. Test Port Availability
        test_port = 8999
        log(f"\n[Test 8] Checking port availability: {test_port}...")
        port_res = await check_port_availability(test_port)
        log(port_res)

        # 10. Test Image Upgrades (New)
        log(f"\n[Test 9] Finding newer tags for {image_name}...")
        from app.services.docker import find_newer_image_tags, summarize_log_patterns
        
        # This might fail if image is custom/private or connection issues
        upgrade_res = await find_newer_image_tags(image_name)
        log(upgrade_res)
        
        # 11. Test Log Summary (New)
        log(f"\n[Test 10] Summarizing 'info' logs in {target_container}...")
        log_sum = await summarize_log_patterns(target_container, "info", minutes=60)
        log(log_sum)
        
        log("\n✅ Verification Complete.")

if __name__ == "__main__":
    asyncio.run(main())
