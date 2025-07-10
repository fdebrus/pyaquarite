import logging
import aiohttp
import asyncio
import json
import copy
from typing import Any

from .auth import AquariteAuth
from .exceptions import RequestError

HAYWARD_API = "https://europe-west1-hayward-europe.cloudfunctions.net/"
_LOGGER = logging.getLogger(__name__)

def get_pool_name(pool_doc):
    """Utility to extract pool name safely."""
    form = pool_doc.get("form", {})
    names = form.get("names")
    if names and isinstance(names, list) and names:
        return names[0].get("name", "Unknown")
    return form.get("name", "Unknown")

class AquariteAPI:
    def __init__(self, auth: AquariteAuth, session: aiohttp.ClientSession = None):
        self.auth = auth
        self.session = session or aiohttp.ClientSession()
        _LOGGER.debug("AquariteAPI initialized with auth: %s", auth)

    async def get_pools(self):
        _LOGGER.debug("Fetching pools for user: %s", self.auth.tokens.get("localId"))
        client = self.auth.client
        # Async Firestore call, fallback to to_thread if needed
        user_dict = await asyncio.to_thread(
            lambda: client.collection("users").document(self.auth.tokens["localId"]).get().to_dict()
        )
        _LOGGER.debug("User document retrieved: %s", user_dict)
        pools = {}
        for pool_id in user_dict.get("pools", []):
            _LOGGER.debug("Fetching data for pool_id: %s", pool_id)
            pool_doc = await asyncio.to_thread(
                lambda: client.collection("pools").document(pool_id).get().to_dict()
            )
            name = get_pool_name(pool_doc)
            pools[pool_id] = name
            _LOGGER.debug("Pool added: %s -> %s", pool_id, name)
        return pools

    async def get_pool_data(self, pool_id: str):
        _LOGGER.debug("Fetching full data for pool_id: %s", pool_id)
        client = self.auth.client
        pool_data = await asyncio.to_thread(
            lambda: client.collection("pools").document(pool_id).get().to_dict()
        )
        _LOGGER.debug("Pool data retrieved: %s", pool_data)
        return pool_data

    async def send_command(self, data):
        _LOGGER.debug("Sending command with data: %s", data)
        headers = {
            "Authorization": f"Bearer {self.auth.tokens['idToken']}",
            "Accept": "application/json"
        }
        url = f"{HAYWARD_API}sendPoolCommand"
        async with self.session.post(url, json=data, headers=headers) as response:
            _LOGGER.debug("Command response status: %s", response.status)
            if response.status == 200:
                return
            text = await response.text()
            _LOGGER.error("Command failed with status %s: %s", response.status, text)
            raise RequestError(f"Command failed with status {response.status}: {text}")

    async def set_value(self, pool_id: str, value_path: str, value: Any) -> None:
        try:
            pool_data = await self.get_pool_data(pool_id)
            path_parts = value_path.split('.')
            top_key = path_parts[0]

            original_obj = copy.deepcopy(pool_data.get(top_key, {}))
            if not original_obj:
                raise ValueError(f"No data for key '{top_key}' in pool data.")

            temp = original_obj
            for key in path_parts[1:-1]:
                temp = temp.setdefault(key, {})
            temp[path_parts[-1]] = value

            changes_dict = {top_key: original_obj}
            payload = {
                "gateway": pool_data.get("wifi"),
                "poolId": pool_id,
                "operation": "WRP",
                "operationId": None,
                "changes": json.dumps(changes_dict),
                "pool": None,
                "source": "web"
            }

            _LOGGER.debug("Setting %s to %s for pool ID %s --- %s", value_path, value, pool_id, payload)
            await self.send_command(payload)
        except Exception as e:
            _LOGGER.error("Failed to set value for pool ID %s: %s", pool_id, e)
            raise

    async def close(self):
        _LOGGER.debug("Closing aiohttp session.")
        await self.session.close()
