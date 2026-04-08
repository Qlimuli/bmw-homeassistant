"""BMW CarData MQTT Client for real-time streaming."""
from __future__ import annotations

import asyncio
import json
import logging
import ssl
from typing import TYPE_CHECKING, Any

import paho.mqtt.client as mqtt

from homeassistant.core import HomeAssistant

from .const import (
    BMW_MQTT_HOST,
    BMW_MQTT_PORT,
    MQTT_KEEPALIVE,
    DEBUG_LOG,
)

if TYPE_CHECKING:
    from . import BMWCarDataCoordinator

_LOGGER = logging.getLogger(__name__)


class BMWMQTTClient:
    """MQTT Client for BMW CarData streaming."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: "BMWCarDataCoordinator",
        gcid: str,
        id_token: str,
        custom_broker: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the MQTT client."""
        self.hass = hass
        self.coordinator = coordinator
        self._gcid = gcid
        self._id_token = id_token
        self._custom_broker = custom_broker

        self._client: mqtt.Client | None = None
        self._connected = False
        self._reconnect_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._subscribed_vins: set[str] = set()

        # Circuit breaker for reconnection
        self._consecutive_failures = 0
        self._max_failures = 5
        self._backoff_base = 5  # seconds
        self._max_backoff = 300  # 5 minutes

    @property
    def is_connected(self) -> bool:
        """Return connection status."""
        return self._connected

    def update_tokens(self, id_token: str, gcid: str | None = None) -> None:
        """Update tokens for reconnection."""
        self._id_token = id_token
        if gcid:
            self._gcid = gcid

    async def async_start(self) -> None:
        """Start the MQTT client."""
        if not self._gcid or not self._id_token:
            _LOGGER.warning("Cannot start MQTT: missing GCID or ID token")
            return

        self._stop_event.clear()
        await self._async_connect()

    async def async_stop(self) -> None:
        """Stop the MQTT client."""
        self._stop_event.set()

        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

        if self._client:
            self._client.disconnect()
            self._client.loop_stop()
            self._client = None

        self._connected = False
        _LOGGER.info("BMW MQTT client stopped")

    async def _async_connect(self) -> None:
        """Connect to the MQTT broker."""
        try:
            # Use custom broker or BMW's broker
            if self._custom_broker:
                host = self._custom_broker.get("host", BMW_MQTT_HOST)
                port = self._custom_broker.get("port", BMW_MQTT_PORT)
                use_tls = self._custom_broker.get("tls", True)
            else:
                host = BMW_MQTT_HOST
                port = BMW_MQTT_PORT
                use_tls = True

            # Create MQTT client with paho-mqtt 2.x API
            # BMW's streaming endpoint on port 9000 uses MQTT-over-WebSocket (WSS)
            self._client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=f"bmw_cardata_{self._gcid[:8]}",
                protocol=mqtt.MQTTv311,
                transport="websockets",
            )

            # Set callbacks
            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect
            self._client.on_message = self._on_message

            # Configure TLS
            # ssl.create_default_context() performs blocking disk I/O (loading CA certs),
            # so it must run in an executor to avoid blocking the HA event loop.
            if use_tls:
                ssl_context = await self.hass.async_add_executor_job(
                    ssl.create_default_context
                )
                ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
                ssl_context.check_hostname = True
                ssl_context.verify_mode = ssl.CERT_REQUIRED
                self._client.tls_set_context(ssl_context)
                # BMW's broker requires the Bearer token in the HTTP Upgrade request
                # headers (in addition to MQTT username/password credentials).
                self._client.ws_set_options(
                    path="/mqtt",
                    headers={"Authorization": f"Bearer {self._id_token}"},
                )

            # Set credentials for BMW broker
            if not self._custom_broker:
                self._client.username_pw_set(self._gcid, self._id_token)
            elif self._custom_broker.get("username"):
                self._client.username_pw_set(
                    self._custom_broker["username"],
                    self._custom_broker.get("password", ""),
                )

            # Connect in executor to avoid blocking
            await self.hass.async_add_executor_job(
                self._client.connect, host, port, MQTT_KEEPALIVE
            )

            # Start the loop
            self._client.loop_start()

            _LOGGER.info("BMW MQTT client connecting to %s:%s", host, port)

        except Exception as err:
            _LOGGER.error("Failed to connect to BMW MQTT: %s", err)
            await self._schedule_reconnect()

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None = None,
    ) -> None:
        """Handle MQTT connection (paho-mqtt 2.x callback signature)."""
        if not reason_code.is_failure:
            self._connected = True
            self._consecutive_failures = 0
            _LOGGER.info("BMW MQTT client connected")

            # Subscribe to vehicle topics
            self._subscribe_to_vehicles()
        else:
            _LOGGER.error("BMW MQTT connection failed with reason: %s", reason_code)
            self._connected = False
            # Schedule reconnect
            asyncio.run_coroutine_threadsafe(
                self._schedule_reconnect(),
                self.hass.loop,
            )

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        disconnect_flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None = None,
    ) -> None:
        """Handle MQTT disconnection (paho-mqtt 2.x callback signature)."""
        self._connected = False

        if reason_code.is_failure:
            _LOGGER.warning(
                "BMW MQTT client disconnected unexpectedly (reason=%s)", reason_code
            )
            # Schedule reconnect
            asyncio.run_coroutine_threadsafe(
                self._schedule_reconnect(),
                self.hass.loop,
            )
        else:
            _LOGGER.info("BMW MQTT client disconnected gracefully")

    def _on_message(
        self,
        client: mqtt.Client,
        userdata: Any,
        msg: mqtt.MQTTMessage,
    ) -> None:
        """Handle incoming MQTT message."""
        try:
            # Parse topic: {GCID}/{VIN}
            topic_parts = msg.topic.split("/")
            if len(topic_parts) >= 2:
                vin = topic_parts[-1]
            else:
                vin = None

            # Parse payload
            payload = json.loads(msg.payload.decode())

            # Extract VIN from payload if not in topic
            if not vin:
                vin = payload.get("vin")

            if not vin:
                if DEBUG_LOG:
                    _LOGGER.debug("Received message without VIN: %s", msg.topic)
                return

            # Extract data
            data = payload.get("data", {})
            timestamp = payload.get("timestamp")

            if DEBUG_LOG:
                _LOGGER.debug(
                    "MQTT message for VIN %s: %s descriptors",
                    vin,
                    len(data),
                )

            # Process each data point
            processed_data = {}
            for descriptor, value_data in data.items():
                if isinstance(value_data, dict):
                    processed_data[descriptor] = {
                        "value": value_data.get("value"),
                        "unit": value_data.get("unit"),
                        "timestamp": value_data.get("timestamp", timestamp),
                    }
                else:
                    processed_data[descriptor] = {
                        "value": value_data,
                        "timestamp": timestamp,
                    }

            # Update coordinator
            asyncio.run_coroutine_threadsafe(
                self._async_update_coordinator(vin, processed_data),
                self.hass.loop,
            )

        except json.JSONDecodeError as err:
            _LOGGER.error("Failed to parse MQTT message: %s", err)
        except Exception as err:
            _LOGGER.error("Error processing MQTT message: %s", err)

    async def _async_update_coordinator(
        self,
        vin: str,
        data: dict[str, Any],
    ) -> None:
        """Update the coordinator with new data."""
        self.coordinator.update_mqtt_data(vin, data)

    def _subscribe_to_vehicles(self) -> None:
        """Subscribe to vehicle topics."""
        if not self._client or not self._connected:
            return

        # Get vehicles from coordinator
        vehicles = self.coordinator.get_all_vehicles()

        # Subscribe to each vehicle's topic
        for vin in vehicles:
            topic = f"{self._gcid}/{vin}"
            if vin not in self._subscribed_vins:
                self._client.subscribe(topic, qos=1)
                self._subscribed_vins.add(vin)
                _LOGGER.info("Subscribed to BMW MQTT topic for VIN %s", vin[-4:])

        # Also subscribe to wildcard if no specific VINs
        if not vehicles:
            topic = f"{self._gcid}/#"
            self._client.subscribe(topic, qos=1)
            _LOGGER.info("Subscribed to BMW MQTT wildcard topic")

    def add_vehicle_subscription(self, vin: str) -> None:
        """Add subscription for a new vehicle."""
        if self._client and self._connected and vin not in self._subscribed_vins:
            topic = f"{self._gcid}/{vin}"
            self._client.subscribe(topic, qos=1)
            self._subscribed_vins.add(vin)
            _LOGGER.info("Added BMW MQTT subscription for VIN %s", vin[-4:])

    async def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt."""
        if self._stop_event.is_set():
            return

        self._consecutive_failures += 1

        if self._consecutive_failures > self._max_failures:
            _LOGGER.error(
                "BMW MQTT: Too many consecutive failures (%s), stopping reconnection",
                self._consecutive_failures,
            )
            return

        # Calculate backoff delay
        delay = min(
            self._backoff_base * (2 ** (self._consecutive_failures - 1)),
            self._max_backoff,
        )

        _LOGGER.info(
            "BMW MQTT: Scheduling reconnection in %s seconds (attempt %s)",
            delay,
            self._consecutive_failures,
        )

        await asyncio.sleep(delay)

        if not self._stop_event.is_set():
            # Refresh token before reconnecting
            try:
                await self.coordinator.api.async_refresh_tokens()
                self._id_token = self.coordinator.api.id_token or self._id_token
            except Exception as err:
                _LOGGER.error("Failed to refresh token for MQTT: %s", err)

            await self._async_connect()

    async def async_refresh_connection(self) -> None:
        """Refresh the connection with new credentials."""
        _LOGGER.info("Refreshing BMW MQTT connection with new credentials")

        # Stop current connection
        if self._client:
            self._client.disconnect()
            self._client.loop_stop()
            self._client = None

        self._connected = False
        self._subscribed_vins.clear()

        # Get fresh tokens
        try:
            await self.coordinator.api.async_refresh_tokens()
            self._id_token = self.coordinator.api.id_token or self._id_token
            self._gcid = self.coordinator.api.gcid or self._gcid
        except Exception as err:
            _LOGGER.error("Failed to refresh tokens: %s", err)

        # Reconnect
        await self._async_connect()
