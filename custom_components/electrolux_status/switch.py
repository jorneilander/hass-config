"""Switch platform for Electrolux Status."""
from homeassistant.components.switch import SwitchEntity

from pyelectroluxocp import OneAppApi
from .const import SWITCH, DOMAIN
from .entity import ElectroluxEntity
import logging

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Setup sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    appliances = coordinator.data.get('appliances', None)
    if appliances is not None:
        for appliance_id, appliance in appliances.appliances.items():
            entities = [entity for entity in appliance.entities if entity.entity_type == SWITCH]
            _LOGGER.debug("Electrolux add %d sensors to registry for appliance %s", len(entities), appliance_id)
            async_add_entities(entities)


class ElectroluxSwitch(ElectroluxEntity, SwitchEntity):
    """Electrolux Status switch class."""

    @property
    def is_on(self):
        """Return true if the binary_sensor is on."""
        value = self.extract_value()

        # Electrolux bug
        if value is not None and isinstance(value, str):
            if value == "ON":
                value = True
            else:
                value = False

        if value is None:
            return self._cached_value
        else:
            self._cached_value = value
        return value

    async def switch(self, value: bool):
        client: OneAppApi = self.api
        # Electrolux bug
        if "values" in self.capability:
            if value:
                value = "ON"
            else:
                value = "OFF"

        if self.entity_source:
            command = {self.entity_source: {self.entity_attr: value}}
        else:
            command = {self.entity_attr: value}
        _LOGGER.debug("Electrolux set value %f", value)
        result = await client.execute_appliance_command(self.pnc_id, command)
        _LOGGER.debug("Electrolux set value result %s", result)

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self.switch(True)

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.switch(False)
