import httpx
import asyncio

URL = "https://www.uber.com/blog/enhanced-agentic-rag/?uclick_id=d3d8544d-44e6-4599-a32b-35a5f3439bad"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1"
}
TIMEOUT = 30.0

async def main():
    print(f"Attempting to connect to {URL} with timeout {TIMEOUT}s...")
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
            response = await client.get(URL)
            response.raise_for_status()
            print(f"SUCCESS! Status Code: {response.status_code}")
            print(f"Final URL: {response.url}")
    except httpx.RequestError as exc:
        print(f"FAILURE: An error occurred while requesting {exc.request.url!r}.")
        print(f"Error details: {exc}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 