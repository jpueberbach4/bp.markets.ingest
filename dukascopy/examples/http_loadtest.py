import asyncio
import aiohttp
import time

URL = "http://localhost:8000/ohlcv/1.1/select/BTC-USD,1m[macd(12,6,9):rsi(14):is-open():zigzag(0.5)]/after/1764144000000/output/JSON?limit=1000&subformat=3&order=asc"
CONCURRENCY = 64
TOTAL_REQUESTS = 1000

async def fetch(session, semaphore, stats):
    async with semaphore:
        try:
            start_time = time.perf_counter()
            async with session.get(URL) as response:
                status = response.status
                await response.read() 
                end_time = time.perf_counter()
                
                stats['latencies'].append(end_time - start_time)
                stats['codes'][status] = stats['codes'].get(status, 0) + 1
        except Exception as e:
            stats['errors'] += 1

async def main():
    semaphore = asyncio.Semaphore(CONCURRENCY)
    stats = {'latencies': [], 'codes': {}, 'errors': 0}
    
    print(f"🚀 Starting Load Test: {TOTAL_REQUESTS} requests, {CONCURRENCY} concurrent...")
    start_all = time.perf_counter()
    
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(session, semaphore, stats) for _ in range(TOTAL_REQUESTS)]
        await asyncio.gather(*tasks)
        
    end_all = time.perf_counter()
    duration = end_all - start_all
    
    # STATS CALCULATIONS
    rps = TOTAL_REQUESTS / duration
    avg_lat = sum(stats['latencies']) / len(stats['latencies']) if stats['latencies'] else 0
    
    print("\n" + "="*30)
    print(f"🏁 TEST COMPLETE")
    print(f"Total Time:     {duration:.2f}s")
    print(f"Requests/sec:   {rps:.2f}")
    print(f"Avg Latency:    {avg_lat*1000:.2f}ms")
    print(f"Status Codes:   {stats['codes']}")
    print(f"Errors:         {stats['errors']}")
    print("="*30)

if __name__ == "__main__":
    asyncio.run(main())