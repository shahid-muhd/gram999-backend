# app/lean_auth.py
import requests
import time
from django.conf import settings
from django.core.cache import cache

LEAN_AUTH_URL = "https://auth.sandbox.leantech.me/oauth2/token"


class LeanTokenManager:
    CACHE_KEY = "lean_access_token"
    CACHE_EXPIRY_KEY = "lean_access_token_expiry"

    @classmethod
    def get_access_token(cls):
        """
        Returns a valid Lean access token (cached in Redis).
        If expired or not found, fetches a new one.
        """
        token = cache.get(cls.CACHE_KEY)
        expiry = cache.get(cls.CACHE_EXPIRY_KEY)

        if token and expiry and expiry > time.time():
            return token

        # Otherwise, fetch a new token
        return cls._fetch_new_token()

    @classmethod
    def _fetch_new_token(cls):
        data = {
            "client_id": settings.LEAN_CLIENT_ID,
            "client_secret": settings.LEAN_CLIENT_SECRET,
            "grant_type": "client_credentials",
            "scope": "api",
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        resp = requests.post(LEAN_AUTH_URL, data=data, headers=headers, timeout=15)
        resp.raise_for_status()
        token_data = resp.json()

        access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)
        print('fetched new lean access token>>>')
        # Store in Redis slightly less than expiry (safety buffer 30s)
        expiry_timestamp = time.time() + expires_in - 30
        cache.set(cls.CACHE_KEY, access_token, timeout=expires_in)
        cache.set(cls.CACHE_EXPIRY_KEY, expiry_timestamp, timeout=expires_in)

        return access_token


class LeanCustomerToken:
    @staticmethod
    def get_customer_token(customer_id: str) -> dict:
        """
        Generate a customer-scoped access token for use in LinkSDK.
        This is *not* cached. Always fetch fresh from Lean.
        """
        data = {
            "client_id": settings.LEAN_CLIENT_ID,
            "client_secret": settings.LEAN_CLIENT_SECRET,
            "grant_type": "client_credentials",
            "scope": f"customer.{customer_id}",
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        resp = requests.post(LEAN_AUTH_URL, data=data, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()  # contains access_token, expires_in, token_type
