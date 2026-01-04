
import asyncio
import httpx

async def check_health():
    # Try both common ports
    ports = [8000, 8001]
    
    for port in ports:
        url = f"http://localhost:{port}/health"
        print(f"Testing {url}...")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=2.0)
                if resp.status_code == 200:
                    print(f"✅ ALIVE on port {port}!")
                    print(f"   Response: {resp.json()}")
                    return
        except Exception as e:
            print(f"   ❌ Port {port}: No connection")

if __name__ == "__main__":
    asyncio.run(check_health())
