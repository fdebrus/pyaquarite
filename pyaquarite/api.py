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
        url = f"{HAYWARD_API}/sendPoolCommand"
        async with self.session.post(url, json=data, headers=headers) as resp:
            content_type = resp.headers.get("Content-Type", "")
            text = await resp.text()
            _LOGGER.debug("Command response status: %s", resp.status)
            _LOGGER.debug("Command response content-type: %s", content_type)
            _LOGGER.debug("Command response body: %s", text)
            if resp.status != 200:
                _LOGGER.error("Request failed with status %s: %s", resp.status, text)
                raise RequestError(f"Command failed with status {resp.status}: {text}")
            if "application/json" in content_type:
                return json.loads(text)
            else:
                _LOGGER.error(
                    "Unexpected response type: %s. Body: %s", content_type, text
                )
                raise RequestError(f"Unexpected response type: {content_type}. Body: {text}")

    async def set_value(self, pool_id: str, value_path: str, value: Any) -> None:
        try:
            # 1. Get latest pool data
            pool_data = await self.get_pool_data(pool_id)

            # 2. Find the top-level key (e.g. "light", "filtration")
            path_parts = value_path.split('.')
            top_key = path_parts[0]

            # 3. Get the full original object to match the app
            original_obj = copy.deepcopy(pool_data.get(top_key, {}))
            if not original_obj:
                raise ValueError(f"No data for key '{top_key}' in pool data.")

            # 4. Set the nested value
            temp = original_obj
            for key in path_parts[1:-1]:
                temp = temp.setdefault(key, {})
            temp[path_parts[-1]] = value

            # 5. Build the changes dict as {top_key: updated_obj}
            changes_dict = {top_key: original_obj}

            # 6. Construct the full command payload just like the app
            payload = {
                "gateway": pool_data.get("wifi"),
                "poolId": pool_id,
                "operation": "WRP",
                "operationId": None,
                "changes": json.dumps(changes_dict),
                "pool": None,
                "source": "web"
            }

            _LOGGER.debug(f"Setting {value_path} to {value} for pool ID {pool_id} --- {payload}")
            await self.send_command(payload)
        except Exception as e:
            _LOGGER.error(f"Failed to set value for pool ID {pool_id}: {e}")
            raise

    async def close(self):
        _LOGGER.debug("Closing aiohttp session.")
        await self.session.close()
