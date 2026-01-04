import asyncio
import httpx

async def test():
    base_url = "http://localhost:5678/api/v1"
    
    print(f"Base URL: {base_url}")
    
    async with httpx.AsyncClient(base_url=base_url) as client:
        # Test 1: Leading slash
        req1 = client.build_request("GET", "/workflows")
        print(f"Test 1 ('/workflows'): {req1.url}")
        
        # Test 2: No leading slash
        req2 = client.build_request("GET", "workflows")
        print(f"Test 2 ('workflows'):  {req2.url}")

if __name__ == "__main__":
    asyncio.run(test())
