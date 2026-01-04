import asyncio
import httpx
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())
from app.core.config import settings

async def test():
    print("Testing trailing slash hypothesis...")
    
    headers = {
        "X-N8N-API-KEY": settings.n8n_api_key,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    with open("results.txt", "w") as f:
        # URL 1: No slash
        url1 = f"{settings.api_url}workflows"
        print(f"1. GET {url1}")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url1, headers=headers)
                f.write(f"NO_SLASH: {resp.status_code}\n")
        except Exception as e:
            f.write(f"NO_SLASH_ERROR: {e}\n")
        
        # URL 2: With slash
        url2 = f"{settings.api_url}workflows/"
        print(f"2. GET {url2}")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url2, headers=headers)
                f.write(f"WITH_SLASH: {resp.status_code}\n")
        except Exception as e:
            f.write(f"WITH_SLASH_ERROR: {e}\n")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test())
