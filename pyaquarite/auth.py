import aiohttp
import asyncio
import datetime
import json
from google.oauth2.credentials import Credentials
from google.cloud.firestore_v1 import Client as FirestoreClient
from .exceptions import AuthenticationError

class AquariteAuth:
    BASE_URL = "https://identitytoolkit.googleapis.com/v1/accounts"
    TOKEN_URL = "https://securetoken.googleapis.com/v1/token"
    API_KEY = "AIzaSyBLaxiyZ2nS1KgRBqWe-NY4EG7OzG5fKpE"

    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.tokens = None
        self.expiry = None
        self.credentials = None
        self.client = None
        self.session = aiohttp.ClientSession()

    async def authenticate(self):
        url = f"{self.BASE_URL}:signInWithPassword?key={self.API_KEY}"
        data = json.dumps({
            "email": self.email,
            "password": self.password,
            "returnSecureToken": True
        })
        async with self.session.post(url, data=data) as resp:
            if resp.status == 400:
                raise AuthenticationError("Invalid email or password.")
            self.tokens = await resp.json()
            self.expiry = datetime.datetime.now() + datetime.timedelta(seconds=int(self.tokens["expiresIn"]))
            self.credentials = Credentials(
                token=self.tokens['idToken'],
                refresh_token=self.tokens['refreshToken'],
                token_uri=self.TOKEN_URL
            )
            self.client = FirestoreClient(project="hayward-europe", credentials=self.credentials)

    async def close(self):
        await self.session.close()
