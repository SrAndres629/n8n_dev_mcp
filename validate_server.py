
import asyncio
import httpx
import sys

# Color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

async def check_health():
    url = "http://localhost:8000/health"
    print(f"Testing Server Health at: {url}")
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                print(f"{GREEN}✅ SUCCESS: Server is ONLINE{RESET}")
                print(f"   Version: {data.get('version')}")
                print(f"   n8n Status: {data.get('n8n_connection')}")
                return True
            else:
                print(f"{RED}❌ ERROR: Server returned {resp.status_code}{RESET}")
                return False
        except Exception as e:
            print(f"{RED}❌ ERROR: Could not connect to server.{RESET}")
            print(f"   Details: {e}")
            print("\n   Make sure you have started the server using 'start_server.bat'")
            return False

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(check_health())
