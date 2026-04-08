"""BMW CarData API Client."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import secrets
import time
from typing import Any

import aiohttp

from .const import (
    BMW_AUTH_URL,
    BMW_API_URL,
    API_TIMEOUT,
    TOKEN_REFRESH_MARGIN,
    OAUTH_SCOPES,
    OAUTH_RESPONSE_TYPE,
    OAUTH_GRANT_TYPE_DEVICE,
    OAUTH_GRANT_TYPE_REFRESH,
    OAUTH_CODE_CHALLENGE_METHOD,
    DEBUG_LOG,
)

_LOGGER = logging.getLogger(__name__)


class BMWCarDataAPIError(Exception):
    """Base exception for BMW CarData API errors."""
    pass


class BMWCarDataAuthError(BMWCarDataAPIError):
    """Authentication error."""
    pass


class BMWCarDataRateLimitError(BMWCarDataAPIError):
    """Rate limit exceeded error."""
    pass


class BMWCarDataAPI:
    """BMW CarData API Client."""
    
    def __init__(
        self,
        session: aiohttp.ClientSession,
        client_id: str,
        refresh_token: str | None = None,
        access_token: str | None = None,
        id_token: str | None = None,
        gcid: str | None = None,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._client_id = client_id
        self._refresh_token = refresh_token
        self._access_token = access_token
        self._id_token = id_token
        self._gcid = gcid
        self._token_expiry: float = 0
        self._code_verifier: str | None = None
        self._device_code: str | None = None
        self._containers: list[dict[str, Any]] = []
    
    @property
    def access_token(self) -> str | None:
        """Get the current access token."""
        return self._access_token
    
    @property
    def id_token(self) -> str | None:
        """Get the current ID token."""
        return self._id_token
    
    @property
    def gcid(self) -> str | None:
        """Get the GCID."""
        return self._gcid
    
    @property
    def refresh_token(self) -> str | None:
        """Get the refresh token."""
        return self._refresh_token
    
    def _generate_code_verifier(self) -> str:
        """Generate a PKCE code verifier."""
        return secrets.token_urlsafe(64)[:128]
    
    def _generate_code_challenge(self, verifier: str) -> str:
        """Generate a PKCE code challenge from the verifier."""
        digest = hashlib.sha256(verifier.encode()).digest()
        return base64.urlsafe_b64encode(digest).decode().rstrip("=")
    
    async def async_request_device_code(self) -> dict[str, Any]:
        """Request device code for OAuth2 Device Authorization Grant."""
        self._code_verifier = self._generate_code_verifier()
        code_challenge = self._generate_code_challenge(self._code_verifier)
        
        url = f"{BMW_AUTH_URL}/device/code"
        
        data = {
            "client_id": self._client_id,
            "response_type": OAUTH_RESPONSE_TYPE,
            "scope": OAUTH_SCOPES,
            "code_challenge": code_challenge,
            "code_challenge_method": OAUTH_CODE_CHALLENGE_METHOD,
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        
        try:
            async with self._session.post(
                url, data=data, headers=headers, timeout=API_TIMEOUT
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    raise BMWCarDataAuthError(
                        f"Failed to request device code: {response.status} - {text}"
                    )
                
                result = await response.json()
                self._device_code = result.get("device_code")
                
                if DEBUG_LOG:
                    _LOGGER.debug("Device code response: %s", result)
                
                return result
                
        except aiohttp.ClientError as err:
            raise BMWCarDataAPIError(f"Connection error: {err}") from err
    
    async def async_poll_for_token(self) -> dict[str, Any]:
        """Poll for the access token after user authorization."""
        if not self._device_code or not self._code_verifier:
            raise BMWCarDataAuthError("Device code flow not initiated")
        
        url = f"{BMW_AUTH_URL}/token"
        
        data = {
            "client_id": self._client_id,
            "device_code": self._device_code,
            "grant_type": OAUTH_GRANT_TYPE_DEVICE,
            "code_verifier": self._code_verifier,
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        try:
            async with self._session.post(
                url, data=data, headers=headers, timeout=API_TIMEOUT
            ) as response:
                result = await response.json()
                
                if response.status == 400:
                    error = result.get("error", "")
                    if error == "authorization_pending":
                        # User hasn't authorized yet
                        return {"status": "pending"}
                    elif error == "slow_down":
                        return {"status": "slow_down"}
                    elif error == "expired_token":
                        raise BMWCarDataAuthError("Device code expired")
                    else:
                        raise BMWCarDataAuthError(f"Token error: {error}")
                
                if response.status != 200:
                    raise BMWCarDataAuthError(
                        f"Failed to get token: {response.status}"
                    )
                
                # Store tokens
                self._access_token = result.get("access_token")
                self._refresh_token = result.get("refresh_token")
                self._id_token = result.get("id_token")
                self._gcid = result.get("gcid")
                self._token_expiry = time.time() + result.get("expires_in", 3600)
                
                if DEBUG_LOG:
                    _LOGGER.debug("Token obtained successfully")
                
                return {
                    "status": "success",
                    "access_token": self._access_token,
                    "refresh_token": self._refresh_token,
                    "id_token": self._id_token,
                    "gcid": self._gcid,
                    "expires_in": result.get("expires_in"),
                }
                
        except aiohttp.ClientError as err:
            raise BMWCarDataAPIError(f"Connection error: {err}") from err
    
    async def async_refresh_tokens(self) -> bool:
        """Refresh the access and ID tokens."""
        if not self._refresh_token:
            _LOGGER.warning("No refresh token available")
            return False
        
        # Check if refresh is needed
        if self._token_expiry > time.time() + TOKEN_REFRESH_MARGIN:
            return True  # Token still valid
        
        url = f"{BMW_AUTH_URL}/token"
        
        data = {
            "grant_type": OAUTH_GRANT_TYPE_REFRESH,
            "refresh_token": self._refresh_token,
            "client_id": self._client_id,
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        try:
            async with self._session.post(
                url, data=data, headers=headers, timeout=API_TIMEOUT
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    _LOGGER.error("Token refresh failed: %s - %s", response.status, text)
                    raise BMWCarDataAuthError(f"Token refresh failed: {response.status}")
                
                result = await response.json()
                
                # Update tokens
                self._access_token = result.get("access_token")
                self._refresh_token = result.get("refresh_token")
                self._id_token = result.get("id_token")
                self._token_expiry = time.time() + result.get("expires_in", 3600)
                
                if DEBUG_LOG:
                    _LOGGER.debug("Tokens refreshed successfully")
                
                return True
                
        except aiohttp.ClientError as err:
            _LOGGER.error("Token refresh connection error: %s", err)
            raise BMWCarDataAPIError(f"Connection error: {err}") from err
    
    async def _async_api_request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any] | bytes:
        """Make an authenticated API request."""
        # Ensure we have a valid token
        await self.async_refresh_tokens()
        
        if not self._access_token:
            raise BMWCarDataAuthError("No access token available")
        
        url = f"{BMW_API_URL}{endpoint}"
        
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "x-version": "v1",
            "Accept": "application/json",
        }
        
        if data:
            headers["Content-Type"] = "application/json"
        
        try:
            async with self._session.request(
                method,
                url,
                json=data,
                params=params,
                headers=headers,
                timeout=API_TIMEOUT,
            ) as response:
                # Handle rate limit
                if response.status == 429:
                    raise BMWCarDataRateLimitError("API rate limit exceeded")
                
                # Handle errors
                if response.status == 403:
                    result = await response.json()
                    # BMW returns the error code under "exveErrorId" (not "errorId")
                    error_id = result.get("exveErrorId") or result.get("errorId", "")
                    if error_id == "CU-429":
                        raise BMWCarDataRateLimitError(f"Access denied: {result}")
                    raise BMWCarDataAuthError(f"Access denied: {result}")
                
                if response.status == 401:
                    raise BMWCarDataAuthError("Unauthorized")
                
                if response.status >= 400:
                    text = await response.text()
                    raise BMWCarDataAPIError(
                        f"API error {response.status}: {text}"
                    )
                
                # Handle image response
                content_type = response.headers.get("Content-Type", "")
                if "image" in content_type:
                    return await response.read()
                
                if response.status == 204:
                    return {}
                
                return await response.json()
                
        except aiohttp.ClientError as err:
            raise BMWCarDataAPIError(f"Connection error: {err}") from err
    
    async def async_get_vehicle_mappings(self) -> list[dict[str, Any]]:
        """Get all vehicles mapped to the account."""
        result = await self._async_api_request("GET", "/customers/vehicles/mappings")
        
        if isinstance(result, dict):
            return result.get("mappings", [])
        return result if isinstance(result, list) else []
    
    async def async_get_basic_data(self, vin: str) -> dict[str, Any]:
        """Get basic vehicle data."""
        result = await self._async_api_request(
            "GET", f"/customers/vehicles/{vin}/basicData"
        )
        return result if isinstance(result, dict) else {}
    
    async def async_get_containers(self) -> list[dict[str, Any]]:
        """Get all containers."""
        result = await self._async_api_request("GET", "/customers/containers")
        
        if isinstance(result, dict):
            containers = result.get("containers", [])
        elif isinstance(result, list):
            containers = result
        else:
            containers = []
        
        self._containers = containers
        return containers
    
    async def async_create_container(
        self,
        name: str,
        descriptors: list[str],
    ) -> dict[str, Any]:
        """Create a telematic data container."""
        data = {
            "name": name,
            "telematicDataKeys": [
                {"technicalDescriptor": d} for d in descriptors
            ],
        }
        
        result = await self._async_api_request(
            "POST", "/customers/containers", data=data
        )
        return result if isinstance(result, dict) else {}
    
    async def async_delete_container(self, container_id: str) -> bool:
        """Delete a container."""
        await self._async_api_request(
            "DELETE", f"/customers/containers/{container_id}"
        )
        return True
    
    async def async_get_telematic_data(
        self,
        vin: str,
        container_id: str,
    ) -> list[dict[str, Any]]:
        """Get telematic data for a vehicle."""
        result = await self._async_api_request(
            "GET",
            f"/customers/vehicles/{vin}/telematicData",
            params={"containerId": container_id},
        )
        
        if isinstance(result, dict):
            return result.get("telematicData", [])
        return result if isinstance(result, list) else []
    
    async def async_get_charging_history(
        self,
        vin: str,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get charging history for a vehicle."""
        params = {}
        if from_date:
            params["fromDate"] = from_date
        if to_date:
            params["toDate"] = to_date
        
        result = await self._async_api_request(
            "GET",
            f"/customers/vehicles/{vin}/chargingHistory",
            params=params if params else None,
        )
        
        if isinstance(result, dict):
            return result.get("chargingSessions", [])
        return result if isinstance(result, list) else []
    
    async def async_get_vehicle_image(self, vin: str) -> bytes | None:
        """Get vehicle image."""
        try:
            result = await self._async_api_request(
                "GET", f"/customers/vehicles/{vin}/image"
            )
            if isinstance(result, bytes):
                return result
            return None
        except BMWCarDataAPIError:
            return None
    
    async def async_get_tyre_diagnosis(self, vin: str) -> dict[str, Any]:
        """Get tyre diagnosis data."""
        result = await self._async_api_request(
            "GET", f"/customers/vehicles/{vin}/smartMaintenanceTyreDiagnosis"
        )
        return result if isinstance(result, dict) else {}
    
    async def async_get_charging_settings(self, vin: str) -> dict[str, Any]:
        """Get location-based charging settings."""
        result = await self._async_api_request(
            "GET", f"/customers/vehicles/{vin}/locationBasedChargingSettings"
        )
        return result if isinstance(result, dict) else {}
