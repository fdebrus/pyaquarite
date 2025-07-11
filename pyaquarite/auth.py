import aiohttp
import asyncio
import datetime
import json
import os

from google.oauth2.credentials import Credentials
from google.cloud.firestore_v1 import Client as FirestoreClient

from .exceptions import AuthenticationError

class AquariteAuth:
    BASE_URL = "https://identitytoolkit.googleapis.com/v1/accounts"
    TOKEN_URL = "https://securetoken.googleapis.com/v1/token"

    def __init__(self, email: str, password: str, api_key: str = None):
        self.email = email
        self.password = password
        self.api_key = api_key or os.getenv("AQUARITE_API_KEY")
        if not self.api_key:
            raise RuntimeError("API Key not provided and AQUARITE_API_KEY environment variable not set")

        self.tokens = None
        self.expiry = None
        self.credentials = None
        self.client = None
        self.session = aiohttp.ClientSession()

    async def authenticate(self):
        """Authenticate with Aquarite/Google Identity Toolkit and create a Firestore client."""
        url = f"{self.BASE_URL}:signInWithPassword?key={self.api_key}"
        data = json.dumps({
            "email": self.email,
            "password": self.password,
            "returnSecureToken": True
        })
        headers = {"Content-Type": "application/json"}
        async with self.session.post(url, data=data, headers=headers) as resp:
            if resp.status != 200:
                raise AuthenticationError(f"Authentication failed with status {resp.status}: {await resp.text()}")
            self.tokens = await resp.json()
            self.expiry = datetime.datetime.now() + datetime.timedelta(seconds=int(self.tokens["expiresIn"]))
            self.credentials = Credentials(
                token=self.tokens['idToken'],
                refresh_token=self.tokens['refreshToken'],
                token_uri=self.TOKEN_URL
            )
            self.client = FirestoreClient(project="hayward-europe", credentials=self.credentials)

    async def refresh_token(self):
        """Refresh Google ID token using the refresh token."""
        url = f"{self.TOKEN_URL}?key={self.api_key}"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.tokens['refreshToken']
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        async with self.session.post(url, data=data, headers=headers) as resp:
            if resp.status != 200:
                raise AuthenticationError(f"Failed to refresh token. Status {resp.status}: {await resp.text()}")
            refreshed = await resp.json()
            self.tokens['idToken'] = refreshed['id_token']
            self.tokens['refreshToken'] = refreshed['refresh_token']
            self.tokens['expiresIn'] = refreshed['expires_in']
            self.expiry = datetime.datetime.now() + datetime.timedelta(seconds=int(self.tokens["expiresIn"]))
            self.credentials = Credentials(
                token=self.tokens['idToken'],
                refresh_token=self.tokens['refreshToken'],
                token_uri=self.TOKEN_URL
            )
            # Recreate Firestore client with new credentials
            self.client = FirestoreClient(project="hayward-europe", credentials=self.credentials)

    async def get_client(self):
        """Return an authenticated Firestore client, handling authentication and refresh as needed."""
        if not self.client or not self.tokens:
            await self.authenticate()
        else:
            # Refresh if token is about to expire (in 60 seconds or less)
            if self.expiry - datetime.datetime.now() < datetime.timedelta(seconds=60):
                await self.refresh_token()
        return self.client

    async def close(self):
        """Cleanup aiohttp session."""
        await self.session.close()
