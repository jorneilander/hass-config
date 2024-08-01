"""Number platform for Electrolux Status."""
from homeassistant.components.number import NumberEntity
from homeassistant.const import UnitOfTime, UnitOfTemperature
from pyelectroluxocp import OneAppApi

from .const import NUMBER, DOMAIN
from .entity import ElectroluxEntity, time_seconds_to_minutes, time_minutes_to_seconds
import logging

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Setup sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    appliances = coordinator.data.get('appliances', None)
    if appliances is not None:
        for appliance_id, appliance in appliances.appliances.items():
            entities = [entity for entity in appliance.entities if entity.entity_type == NUMBER]
            _LOGGER.debug("Electrolux add %d selects to registry for appliance %s", len(entities), appliance_id)
            async_add_entities(entities)


class ElectroluxNumber(ElectroluxEntity, NumberEntity):
    """Electrolux Status number class."""

    @property
    def native_value(self) -> float | None:
        """Return the value reported by the number."""
        if self.unit == UnitOfTime.SECONDS:
            value = time_seconds_to_minutes(self.extract_value())
        else:
            value = self.extract_value()
        if not value:
            value = self.capability.get("default", None)
        if not value:
            return self._cached_value
        else:
            if self.unit == UnitOfTemperature.CELSIUS:
                value = round(value, 2)
            self._cached_value = value
        return value

    @property
    def native_max_value(self) -> float | None:
        """Return the max value."""
        if self.unit == UnitOfTime.SECONDS:
            return time_seconds_to_minutes(self.capability.get("max", 100))
        return self.capability.get("max", 100)

    @property
    def native_min_value(self) -> float | None:
        """Return the max value."""
        if self.unit == UnitOfTime.SECONDS:
            return time_seconds_to_minutes(self.capability.get("min", 0))
        return self.capability.get("min", 0)

    @property
    def native_step(self) -> float | None:
        """Return the max value."""
        if self.unit == UnitOfTime.SECONDS:
            return time_seconds_to_minutes(self.capability.get("step", 1))
        return self.capability.get("step", 1)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        if self.unit == UnitOfTime.SECONDS:
            value = time_minutes_to_seconds(value)
        client: OneAppApi = self.api
        if self.entity_source:
            command = { self.entity_source: {self.entity_attr: value}}
        else:
            command = {self.entity_attr: value}
        _LOGGER.debug("Electrolux set value %f", value)
        result = await client.execute_appliance_command(self.pnc_id, command)
        _LOGGER.debug("Electrolux set value result %s", result)

    @property
    def native_unit_of_measurement(self):
        if self.unit == UnitOfTime.SECONDS:
            return UnitOfTime.MINUTES
        return self.unit
