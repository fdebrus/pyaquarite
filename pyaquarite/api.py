import logging
import aiohttp
import asyncio
import json
from .auth import AquariteAuth
from .exceptions import RequestError

HAYWARD_API = "https://europe-west1-hayward-europe.cloudfunctions.net/"
_LOGGER = logging.getLogger(__name__)


class AquariteAPI:
    def __init__(self, auth: AquariteAuth):
        self.auth = auth
        self.session = aiohttp.ClientSession()
        _LOGGER.debug("AquariteAPI initialized with auth: %s", auth)

    async def get_pools(self):
        _LOGGER.debug("Fetching pools for user: %s", self.auth.tokens.get("localId"))
        client = self.auth.client
        user_dict = (await asyncio.to_thread(
            client.collection("users").document(self.auth.tokens["localId"]).get)
        ).to_dict()
        _LOGGER.debug("User document retrieved: %s", user_dict)

        pools = {}
        for pool_id in user_dict.get("pools", []):
            _LOGGER.debug("Fetching data for pool_id: %s", pool_id)
            pool_doc = (await asyncio.to_thread(
                client.collection("pools").document(pool_id).get)
            ).to_dict()
            _LOGGER.debug("Pool document: %s", pool_doc)
            try:
                name = pool_doc.get("form", {}).get("names", [{}])[0].get("name", "Unknown")
            except (KeyError, IndexError):
                name = pool_doc.get("form", {}).get("name", "Unknown")
            pools[pool_id] = name
            _LOGGER.debug("Pool added: %s -> %s", pool_id, name)
        return pools

    async def get_pool_data(self, pool_id: str):
        _LOGGER.debug("Fetching full data for pool_id: %s", pool_id)
        client = self.auth.client
        pool_data = (await asyncio.to_thread(
            client.collection("pools").document(pool_id).get)
        ).to_dict()
        _LOGGER.debug("Pool data retrieved: %s", pool_data)
        return pool_data

    async def send_command(self, data):
        _LOGGER.debug("Sending command with data: %s", data)
        headers = {"Authorization": f"Bearer {self.auth.tokens['idToken']}"}
        async with self.session.post(
            f"{HAYWARD_API}/sendPoolCommand", json=data, headers=headers
        ) as resp:
            _LOGGER.debug("Command response status: %s", resp.status)
            if resp.status != 200:
                text = await resp.text()
                _LOGGER.error("Command failed with status %s: %s", resp.status, text)
                raise RequestError(f"Command failed with status {resp.status}: {text}")
            result = await resp.json()
            _LOGGER.debug("Command response JSON: %s", result)
            return result

    def _set_in_dict(self, d, path, value):
        _LOGGER.debug("Setting value in dict. Path: %s, Value: %s", path, value)
        keys = path.split('.')
        for key in keys[:-1]:
            d = d.setdefault(key, {})
        d[keys[-1]] = value

    async def set_value(self, pool_id: str, value_path: str, value):
        _LOGGER.debug("Setting value for pool_id: %s, path: %s, value: %s", pool_id, value_path, value)
        changes = {}
        self._set_in_dict(changes, value_path, value)
        _LOGGER.debug("Changes dict prepared: %s", changes)

        command_data = {
            "poolId": pool_id,
            "operation": "WRP",
            "source": "web",
            "changes": json.dumps(changes)
        }

        pool_data = await self.get_pool_data(pool_id)
        if pool_data and pool_data.get("wifi"):
            command_data["gateway"] = pool_data["wifi"]
            _LOGGER.debug("Gateway added to command data: %s", pool_data["wifi"])

        _LOGGER.debug("Final command data to send: %s", command_data)
        await self.send_command(command_data)

    async def close(self):
        _LOGGER.debug("Closing aiohttp session.")
        await self.session.close()
