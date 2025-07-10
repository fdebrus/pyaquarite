import aiohttp
import asyncio
import json
from .auth import AquariteAuth
from .exceptions import RequestError

HAYWARD_API = "https://europe-west1-hayward-europe.cloudfunctions.net/"

class AquariteAPI:
    def __init__(self, auth: AquariteAuth):
        self.auth = auth
        self.session = aiohttp.ClientSession()

    async def get_pools(self):
        client = self.auth.client
        user_dict = (await asyncio.to_thread(
            client.collection("users").document(self.auth.tokens["localId"]).get)
        ).to_dict()
        pools = {}
        for pool_id in user_dict.get("pools", []):
            pool_doc = (await asyncio.to_thread(
                client.collection("pools").document(pool_id).get)
            ).to_dict()
            try:
                name = pool_doc.get("form", {}).get("names", [{}])[0].get("name", "Unknown")
            except (KeyError, IndexError):
                name = pool_doc.get("form", {}).get("name", "Unknown")
            pools[pool_id] = name
        return pools

    async def get_pool_data(self, pool_id: str):
        client = self.auth.client
        pool_data = (await asyncio.to_thread(
            client.collection("pools").document(pool_id).get)
        ).to_dict()
        return pool_data

    async def send_command(self, data):
        headers = {"Authorization": f"Bearer {self.auth.tokens['idToken']}"}
        async with self.session.post(
            f"{HAYWARD_API}/sendPoolCommand", json=data, headers=headers
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RequestError(f"Command failed with status {resp.status}: {text}")
            return await resp.json()

    def _set_in_dict(self, d, path, value):
        """Set value in nested dict using dot notation path."""
        keys = path.split('.')
        for key in keys[:-1]:
            d = d.setdefault(key, {})
        d[keys[-1]] = value

    async def set_value(self, pool_id: str, value_path: str, value):
        changes = {}
        self._set_in_dict(changes, value_path, value)
        command_data = {
            "poolId": pool_id,
            "operation": "WRP",
            "source": "web",
            "changes": json.dumps(changes)
        }
        pool_data = await self.get_pool_data(pool_id)
        if pool_data and pool_data.get("wifi"):
            command_data["gateway"] = pool_data["wifi"]
        await self.send_command(command_data)

    async def close(self):
        await self.session.close()
