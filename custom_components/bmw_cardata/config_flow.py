"""Config flow for BMW CarData integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_CLIENT_ID,
    CONF_REFRESH_TOKEN,
    CONF_ACCESS_TOKEN,
    CONF_ID_TOKEN,
    CONF_GCID,
)
from .api import BMWCarDataAPI, BMWCarDataAuthError, BMWCarDataAPIError

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID): str,
    }
)


class BMWCarDataConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BMW CarData."""
    
    VERSION = 1
    
    def __init__(self) -> None:
        """Initialize the config flow."""
        self._client_id: str | None = None
        self._api: BMWCarDataAPI | None = None
        self._device_code_response: dict[str, Any] | None = None
        self._poll_task: asyncio.Task | None = None
    
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            self._client_id = user_input[CONF_CLIENT_ID]
            
            # Check if already configured
            await self.async_set_unique_id(self._client_id)
            self._abort_if_unique_id_configured()
            
            # Initialize API and request device code
            session = async_get_clientsession(self.hass)
            self._api = BMWCarDataAPI(session=session, client_id=self._client_id)
            
            try:
                self._device_code_response = await self._api.async_request_device_code()
                return await self.async_step_authorize()
            except BMWCarDataAuthError as err:
                _LOGGER.error("Authentication error: %s", err)
                errors["base"] = "auth_error"
            except BMWCarDataAPIError as err:
                _LOGGER.error("API error: %s", err)
                errors["base"] = "cannot_connect"
        
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "bmw_portal": "https://www.bmw.de/de-de/mybmw/vehicle-overview",
            },
        )
    
    async def async_step_authorize(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the authorization step."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            # User claims to have authorized, poll for token
            try:
                max_attempts = 30
                for _ in range(max_attempts):
                    result = await self._api.async_poll_for_token()
                    
                    if result.get("status") == "success":
                        # Successfully authenticated
                        return self.async_create_entry(
                            title=f"BMW CarData ({self._client_id[:8]}...)",
                            data={
                                CONF_CLIENT_ID: self._client_id,
                                CONF_ACCESS_TOKEN: result["access_token"],
                                CONF_REFRESH_TOKEN: result["refresh_token"],
                                CONF_ID_TOKEN: result["id_token"],
                                CONF_GCID: result["gcid"],
                            },
                        )
                    elif result.get("status") == "pending":
                        # Still waiting
                        await asyncio.sleep(2)
                    elif result.get("status") == "slow_down":
                        await asyncio.sleep(5)
                    else:
                        break
                
                errors["base"] = "timeout"
                
            except BMWCarDataAuthError as err:
                _LOGGER.error("Authorization error: %s", err)
                errors["base"] = "auth_error"
            except BMWCarDataAPIError as err:
                _LOGGER.error("API error: %s", err)
                errors["base"] = "cannot_connect"
        
        # Show authorization instructions
        verification_uri = self._device_code_response.get(
            "verification_uri_complete",
            self._device_code_response.get("verification_uri", ""),
        )
        user_code = self._device_code_response.get("user_code", "")
        expires_in = self._device_code_response.get("expires_in", 900)
        
        return self.async_show_form(
            step_id="authorize",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={
                "verification_url": verification_uri,
                "user_code": user_code,
                "expires_minutes": str(expires_in // 60),
            },
        )
    
    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> FlowResult:
        """Handle re-authentication."""
        self._client_id = entry_data.get(CONF_CLIENT_ID)
        return await self.async_step_reauth_confirm()
    
    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle re-authentication confirmation."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            # Re-initiate device code flow
            session = async_get_clientsession(self.hass)
            self._api = BMWCarDataAPI(session=session, client_id=self._client_id)
            
            try:
                self._device_code_response = await self._api.async_request_device_code()
                return await self.async_step_authorize()
            except BMWCarDataAuthError as err:
                _LOGGER.error("Re-auth error: %s", err)
                errors["base"] = "auth_error"
        
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({}),
            errors=errors,
        )
    
    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return BMWCarDataOptionsFlowHandler(config_entry)


class BMWCarDataOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for BMW CarData."""
    
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
    
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "enable_mqtt_streaming",
                        default=self.config_entry.options.get(
                            "enable_mqtt_streaming", True
                        ),
                    ): bool,
                    vol.Optional(
                        "enable_charging_history",
                        default=self.config_entry.options.get(
                            "enable_charging_history", False
                        ),
                    ): bool,
                    vol.Optional(
                        "enable_tyre_diagnosis",
                        default=self.config_entry.options.get(
                            "enable_tyre_diagnosis", False
                        ),
                    ): bool,
                    vol.Optional(
                        "poll_interval_minutes",
                        default=self.config_entry.options.get(
                            "poll_interval_minutes", 30
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=5, max=1440)),
                }
            ),
        )
