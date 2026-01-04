import asyncio
import httpx

async def test():
    # Scenario A: No trailing slash (Current implementation)
    base_url_no_slash = "http://localhost:5678/api/v1"
    print(f"Scenario A: base_url='{base_url_no_slash}'")
    async with httpx.AsyncClient(base_url=base_url_no_slash) as client:
        req = client.build_request("GET", "workflows")
        print(f"   -> Result: {req.url}")
        
    print("-" * 20)

    # Scenario B: With trailing slash (Proposed fix)
    base_url_slash = "http://localhost:5678/api/v1/"
    print(f"Scenario B: base_url='{base_url_slash}'")
    async with httpx.AsyncClient(base_url=base_url_slash) as client:
        req = client.build_request("GET", "workflows")
        print(f"   -> Result: {req.url}")

if __name__ == "__main__":
    asyncio.run(test())
