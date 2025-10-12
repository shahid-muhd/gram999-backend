import requests
from django.conf import settings

DIDIT_BASE_URL_V1 = "https://verification.didit.me/v1"
DIDIT_BASE_URL_V2 = "https://verification.didit.me/v2"


class DiditClient:
    def __init__(self, version: str = "v2"):
        """
        version: "v1" or "v2"
        By default, uses v2 for session creation, retrieval, listing.
        Falls back to v1 for status overrides.
        """
        self.api_key = settings.DIDIT_API_KEY
        self.version = version.lower()
        self.base_url = DIDIT_BASE_URL_V2 if self.version == "v2" else DIDIT_BASE_URL_V1
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "x-api-key": self.api_key,
        }

    def _request(self, method, endpoint, **kwargs):
        url = f"{self.base_url}{endpoint}"
        try:
            resp = requests.request(method, url, headers=self.headers, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            print(f"❌ Didit HTTP error: {resp.text}")
            return {"success": False, "error": str(e), "details": resp.text}
        except Exception as e:
            print(f"❌ Didit request error: {e}")
            return {"success": False, "error": str(e)}

    # === Session APIs (v2 preferred) ===

    def create_session(self, payload: dict):
        """Start a new KYC verification session (v2)"""
        return self._request("POST", "/session/", json=payload)

    def get_session(self, session_id: str):
        """Fetch an existing session (v2)"""
        return self._request("GET", f"/session/{session_id}/")

    def list_sessions(self, limit: int = 10, offset: int = 0):
        """List verification sessions (v2)"""
        return self._request("GET", f"/session/?limit={limit}&offset={offset}")

    # === Phone OTP Service (requires v2) ===
    def send_otp(self, payload: dict):
        """List verification sessions (v2)"""
        return self._request("POST", f"/phone/send/", json=payload)

    # === Status Update (requires v1) ===

    def update_session_status(self, session_id: str, status: str, reason: str = None):
        """Update status (only works if using v1)"""
        if self.version != "v1":
            raise ValueError("update_session_status only available in v1 API")

        return self._request(
            "PATCH",
            f"/session/{session_id}/update-status/",
            json={"new_status": status, **({"reason": reason} if reason else {})},
        )
