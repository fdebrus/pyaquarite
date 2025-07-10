# pyaquarite

Python API client for Hayward Aquarite / pool automation.\
Easily integrate your pool devices and automate settings programmatically!

## Quick Start

```python
import asyncio
from pyaquarite import AquariteAPI, AquariteAuth

# Replace with your authentication logic
auth = AquariteAuth(username='your@email.com', password='yourpassword')

async def main():
    api = AquariteAPI(auth)
    pools = await api.get_pools()
    print("Pools:", pools)

    # Set a value (example: turn on the pool light)
    pool_id = list(pools.keys())[0]
    await api.set_value(pool_id, "light.status", True)

    await api.close()

asyncio.run(main())
```
