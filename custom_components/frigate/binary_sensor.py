"""Binary sensor platform for Frigate."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import (
    FrigateEntity,
    FrigateMQTTEntity,
    ReceiveMessage,
    decode_if_necessary,
    get_cameras,
    get_cameras_and_audio,
    get_cameras_zones_and_objects,
    get_friendly_name,
    get_frigate_device_identifier,
    get_frigate_entity_unique_id,
    get_zones,
)
from .const import ATTR_CONFIG, DOMAIN, NAME
from .icons import get_dynamic_icon_from_type

_LOGGER: logging.Logger = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Binary sensor entry setup."""
    frigate_config = hass.data[DOMAIN][entry.entry_id][ATTR_CONFIG]
    entities: list[FrigateEntity] = []

    # Add object sensors for cameras and zones.
    entities.extend(
        [
            FrigateObjectOccupancySensor(entry, frigate_config, cam_name, obj)
            for cam_name, obj in get_cameras_zones_and_objects(frigate_config)
        ]
    )

    # Add audio sensors for cameras.
    entities.extend(
        [
            FrigateAudioSensor(entry, frigate_config, cam_name, audio)
            for cam_name, audio in get_cameras_and_audio(frigate_config)
        ]
    )

    # Add generic motion sensors for cameras.
    entities.extend(
        [
            FrigateMotionSensor(entry, frigate_config, cam_name)
            for cam_name in get_cameras(frigate_config)
        ]
    )

    async_add_entities(entities)


class FrigateObjectOccupancySensor(FrigateMQTTEntity, BinarySensorEntity):
    """Frigate Occupancy Sensor class."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        frigate_config: dict[str, Any],
        cam_name: str,
        obj_name: str,
    ) -> None:
        """Construct a new FrigateObjectOccupancySensor."""
        self._cam_name = cam_name
        self._obj_name = obj_name
        self._is_on = False
        self._frigate_config = frigate_config

        super().__init__(
            config_entry,
            frigate_config,
            {
                "state_topic": {
                    "msg_callback": self._state_message_received,
                    "qos": 0,
                    "topic": (
                        f"{self._frigate_config['mqtt']['topic_prefix']}"
                        f"/{self._cam_name}/{self._obj_name}"
                    ),
                    "encoding": None,
                },
            },
        )

    @callback
    def _state_message_received(self, msg: ReceiveMessage) -> None:
        """Handle a new received MQTT state message."""
        try:
            self._is_on = int(msg.payload) > 0
        except ValueError:
            self._is_on = False
        self.async_write_ha_state()

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return get_frigate_entity_unique_id(
            self._config_entry.entry_id,
            "occupancy_sensor",
            f"{self._cam_name}_{self._obj_name}",
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return {
            "identifiers": {
                get_frigate_device_identifier(self._config_entry, self._cam_name)
            },
            "via_device": get_frigate_device_identifier(self._config_entry),
            "name": get_friendly_name(self._cam_name),
            "model": self._get_model(),
            "configuration_url": f"{self._config_entry.data.get(CONF_URL)}/cameras/{self._cam_name if self._cam_name not in get_zones(self._frigate_config) else ''}",
            "manufacturer": NAME,
        }

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{get_friendly_name(self._obj_name)} occupancy"

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._is_on

    @property
    def device_class(self) -> BinarySensorDeviceClass:
        """Return the device class."""
        return BinarySensorDeviceClass.OCCUPANCY

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return get_dynamic_icon_from_type(self._obj_name, self._is_on)


class FrigateAudioSensor(FrigateMQTTEntity, BinarySensorEntity):
    """Frigate Audio Sensor class."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        frigate_config: dict[str, Any],
        cam_name: str,
        audio_name: str,
    ) -> None:
        """Construct a new FrigateAudioSensor."""
        self._cam_name = cam_name
        self._audio_name = audio_name
        self._is_on = False
        self._frigate_config = frigate_config

        super().__init__(
            config_entry,
            frigate_config,
            {
                "state_topic": {
                    "msg_callback": self._state_message_received,
                    "qos": 0,
                    "topic": (
                        f"{self._frigate_config['mqtt']['topic_prefix']}"
                        f"/{self._cam_name}/audio/{self._audio_name}"
                    ),
                },
            },
        )

    @callback
    def _state_message_received(self, msg: ReceiveMessage) -> None:
        """Handle a new received MQTT state message."""
        self._is_on = decode_if_necessary(msg.payload) == "ON"
        self.async_write_ha_state()

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return get_frigate_entity_unique_id(
            self._config_entry.entry_id,
            "audio_sensor",
            f"{self._cam_name}_{self._audio_name}",
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return {
            "identifiers": {
                get_frigate_device_identifier(self._config_entry, self._cam_name)
            },
            "via_device": get_frigate_device_identifier(self._config_entry),
            "name": get_friendly_name(self._cam_name),
            "model": self._get_model(),
            "configuration_url": f"{self._config_entry.data.get(CONF_URL)}/cameras/{self._cam_name}",
            "manufacturer": NAME,
        }

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._audio_name} sound"

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._is_on

    @property
    def device_class(self) -> BinarySensorDeviceClass:
        """Return the device class."""
        return BinarySensorDeviceClass.SOUND

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return get_dynamic_icon_from_type("sound", self._is_on)


class FrigateMotionSensor(FrigateMQTTEntity, BinarySensorEntity):
    """Frigate Motion Sensor class."""

    _attr_name = "Motion"

    def __init__(
        self,
        config_entry: ConfigEntry,
        frigate_config: dict[str, Any],
        cam_name: str,
    ) -> None:
        """Construct a new FrigateMotionSensor."""
        self._cam_name = cam_name
        self._is_on = False
        self._frigate_config = frigate_config

        super().__init__(
            config_entry,
            frigate_config,
            {
                "state_topic": {
                    "msg_callback": self._state_message_received,
                    "qos": 0,
                    "topic": (
                        f"{self._frigate_config['mqtt']['topic_prefix']}"
                        f"/{self._cam_name}/motion"
                    ),
                },
            },
        )

    @callback
    def _state_message_received(self, msg: ReceiveMessage) -> None:
        """Handle a new received MQTT state message."""
        self._is_on = decode_if_necessary(msg.payload) == "ON"
        self.async_write_ha_state()

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return get_frigate_entity_unique_id(
            self._config_entry.entry_id,
            "motion_sensor",
            f"{self._cam_name}",
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return {
            "identifiers": {
                get_frigate_device_identifier(self._config_entry, self._cam_name)
            },
            "via_device": get_frigate_device_identifier(self._config_entry),
            "name": get_friendly_name(self._cam_name),
            "model": self._get_model(),
            "configuration_url": f"{self._config_entry.data.get(CONF_URL)}/cameras/{self._cam_name if self._cam_name not in get_zones(self._frigate_config) else ''}",
            "manufacturer": NAME,
        }

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._is_on

    @property
    def device_class(self) -> BinarySensorDeviceClass:
        """Return the device class."""
        return BinarySensorDeviceClass.MOTION
