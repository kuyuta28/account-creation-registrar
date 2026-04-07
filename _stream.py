import asyncio, websockets, sys
job_id = sys.argv[1]
async def s():
    uri = f"ws://localhost:8799/api/v1/registration/jobs/{job_id}/logs"
    async with websockets.connect(uri) as ws:
        async for m in ws:
            print(m[:400], flush=True)
asyncio.run(s())
