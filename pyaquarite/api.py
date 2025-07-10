import aiohttp
import asyncio
from .auth import AquariteAuth
from .exceptions import RequestError

HAYWARD_API = "https://europe-west1-hayward-europe.cloudfunctions.net/"

class AquariteAPI:
    def __init__(self, auth: AquariteAuth):
        self.auth = auth
        self.session = aiohttp.ClientSession()

    async def get_pools(self):
        client = self.auth.client
        user_dict = (await asyncio.to_thread(client.collection("users").document(self.auth.tokens["localId"]).get)).to_dict()
        pools = {}
        for pool_id in user_dict.get("pools", []):
            pool_doc = (await asyncio.to_thread(client.collection("pools").document(pool_id).get)).to_dict()
            pools[pool_id] = pool_doc.get("form", {}).get("names", [{}])[0].get("name", "Unknown")
        return pools

    async def get_pool_data(self, pool_id: str):
        client = self.auth.client
        pool_data = (await asyncio.to_thread(client.collection("pools").document(pool_id).get)).to_dict()
        return pool_data

    async def send_command(self, data):
        headers = {"Authorization": f"Bearer {self.auth.tokens['idToken']}"}
        async with self.session.post(f"{HAYWARD_API}/sendPoolCommand", json=data, headers=headers) as resp:
            if resp.status != 200:
                raise RequestError(f"Command failed with status {resp.status}")
            return await resp.json()
            
    async def set_value(self, pool_id: str, value_path: str, value):
        client = self.auth.client
        doc_ref = client.collection("pools").document(pool_id)
        data = await asyncio.to_thread(doc_ref.get)
        pool_data = data.to_dict()
        def set_in_dict(d, path, value):
            keys = path.split('.')
            for key in keys[:-1]:
                d = d.setdefault(key, {})
            d[keys[-1]] = value
        set_in_dict(pool_data, value_path, value)
        command_data = {
            "poolId": pool_id,
            "operation": "WRP",
            "source": "web",
            "changes": {value_path: value}
        }
        await self.send_command(command_data)

    async def close(self):
        await self.session.close()
