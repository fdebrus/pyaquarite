import asyncio
from .api import AquariteAPI

class AquariteCoordinator:
    def __init__(self, api: AquariteAPI, pool_id: str):
        self.api = api
        self.pool_id = pool_id
        self.data = {}

    async def refresh_data(self):
        self.data = await self.api.get_pool_data(self.pool_id)
        return self.data

    async def periodic_refresh(self, interval=60):
        while True:
            await self.refresh_data()
            await asyncio.sleep(interval)
