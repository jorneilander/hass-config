"""electrolux status integration."""
import asyncio
import json
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed

from .api import Appliance, Appliances, ElectroluxLibraryEntity
from .const import DOMAIN
from pyelectroluxocp import OneAppApi

_LOGGER: logging.Logger = logging.getLogger(__package__)

class ElectroluxCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""
    api: OneAppApi = None

    def __init__(self, hass: HomeAssistant, client: OneAppApi, renew_interval: int) -> None:
        """Initialize."""
        self.api = client
        self.platforms = []
        self.renew_task = None
        self.renew_interval = renew_interval

        super().__init__(hass, _LOGGER, name=DOMAIN)

    async def async_login(self) -> bool:
        try:
            # Check that one can extract the appliance list to confirm login
            token = await self.api.get_user_token()
            if token and token.token:
                _LOGGER.debug("Electrolux logged successfully, %s", token.token)
                return True
            _LOGGER.debug("Electrolux wrong credentials")
        except Exception as ex:
            _LOGGER.error("Could not log in to ElectroluxStatus, %s", ex)
            raise ex
        return False

    # async def deferred_update(self, appliance_id: str, delay: int) -> None:
    #     """Deferred update due to Electrolux not sending updated data at the end of the appliance program/cycle"""
    #     _LOGGER.debug("Electrolux scheduling deferred update for appliance %s", appliance_id)
    #     await asyncio.sleep(delay)
    #     _LOGGER.debug("Electrolux scheduled deferred update for appliance %s running", appliance_id)
    #     appliances: Appliances = self.data.get('appliances', None)
    #     # Should not happen : wonder if this is not the cause of infinite loop of integrations creations => disabled
    #     # if appliances is None or len(appliances.get_appliances()) == 0:
    #     #     await self.setup_entities()
    #     #     appliances = self.data.get('appliances', None)
    #
    #     for local_appliance_id in appliances.get_appliances():
    #         if local_appliance_id != appliance_id:
    #             pass
    #         try:
    #             appliance: Appliance = appliances.get_appliances().get(appliance_id)
    #             appliance_status = await self.api.get_appliance_state(appliance_id)
    #             appliance.update(appliance_status)
    #             self.async_set_updated_data(self.data)
    #         except Exception as exception:
    #             _LOGGER.exception(exception)
    #             raise UpdateFailed() from exception

    def incoming_data(self, data: dict[str, dict[str, any]]):
        _LOGGER.debug("Electrolux appliance state updated %s", json.dumps(data))
        # Update reported data
        appliances: Appliances = self.data.get('appliances', None)
        for appliance_id, appliance_data in data.items():
            appliance = appliances.get_appliance(appliance_id)
            appliance.update_reported_data(appliance_data)
        self.async_set_updated_data(self.data)
        # Bug in Electrolux library : no data sent when appliance cycle is over
        # for appliance_id, appliance_data in data.items():
        #     do_deferred = False
        #     for key, value in appliance_data.items():
        #         if key in TIME_ENTITIES_TO_UPDATE:
        #             if value is not None and value > 0 and value <= 1:
        #                 do_deferred = True
        #                 break
        #     if do_deferred:
        #         asyncio.create_task(self.deferred_update(appliance_id, 70))


    def listen_websocket(self):
        appliances: Appliances = self.data.get('appliances', None)
        ids = appliances.get_appliance_ids()
        _LOGGER.debug("Electrolux listen_websocket for appliances %s", ",".join(ids))
        if ids is None or len(ids) == 0:
            return
        asyncio.create_task(self.api.watch_for_appliance_state_updates(ids, self.incoming_data))

    async def launch_websocket_renewal_task(self):
        if self.renew_task:
            self.renew_task.cancel()
            self.renew_task = None
        self.renew_task = asyncio.create_task(self.renew_websocket(), name="Electrolux renewal websocket")

    async def renew_websocket(self):
        while True:
            await asyncio.sleep(self.renew_interval)
            _LOGGER.debug("Electrolux renew_websocket")
            try:
                await self.api.disconnect_websocket()
            except Exception as ex:
                _LOGGER.error("Electrolux renew_websocket could not close websocket %s", ex)
            self.listen_websocket()

    async def close_websocket(self):
        if self.renew_task:
            self.renew_task.cancel()
            self.renew_task = None
        try:
            await self.api.disconnect_websocket()
        except Exception as ex:
            _LOGGER.error("Electrolux close_websocket could not close websocket %s", ex)

    async def setup_entities(self):
        _LOGGER.debug("Electrolux setup_entities")
        appliances = Appliances({})
        self.data = {
            "appliances": appliances
        }
        try:
            appliances_list = await self.api.get_appliances_list()
            if appliances_list is None:
                _LOGGER.error("Electrolux unable to retrieve appliances list. Cancelling setup")
                raise Exception("Electrolux unable to retrieve appliances list. Cancelling setup")
            _LOGGER.debug("Electrolux update appliances %s %s",self.api, json.dumps(appliances_list))
            for appliance_json in appliances_list:
                appliance_capabilities = None
                appliance_id = appliance_json.get('applianceId')
                connection_status = appliance_json.get('connectionState')
                _LOGGER.debug("Electrolux found appliance %s", appliance_id)
                # appliance_profile = await self.hass.async_add_executor_job(self.api.getApplianceProfile, appliance)
                appliance_name = appliance_json.get('applianceData').get('applianceName')
                appliance_infos = await self.api.get_appliances_info([appliance_id])
                appliance_state = await self.api.get_appliance_state(appliance_id)
                _LOGGER.debug("Electrolux get_appliance_status result %s", json.dumps(appliance_state))
                try:
                    appliance_capabilities = await self.api.get_appliance_capabilities(appliance_id)
                    _LOGGER.debug("Electrolux appliance capabilities %s", json.dumps(appliance_capabilities))
                except Exception as exception:
                    _LOGGER.warning("Electrolux unable to retrieve capabilities, we are going on our own")

                appliance_info = None if len(appliance_infos) == 0 else appliance_infos[0]
                appliance_model = appliance_info.get('model') if appliance_info else ""
                brand = appliance_info.get('brand') if appliance_info else ""
                # appliance_profile not reported
                appliance = Appliance(coordinator=self,
                                      pnc_id=appliance_id,
                                      name=appliance_name,
                                      brand=brand,
                                      model=appliance_model,
                                      state=appliance_state)
                appliances.appliances[appliance_id] = appliance

                appliance.setup(ElectroluxLibraryEntity(name=appliance_name, status=connection_status,
                                                        state=appliance_state, appliance_info=appliance_info,
                                                        capabilities=appliance_capabilities))
            return self.data
        except Exception as exception:
            _LOGGER.exception(exception)
            raise UpdateFailed() from exception


    async def _async_update_data(self):
        """Update data via library."""
        appliances: Appliances = self.data.get('appliances', None)
        for appliance_id, appliance in appliances.get_appliances().items():
            try:
                appliance_status = await self.api.get_appliance_state(appliance_id)
                appliance.update(appliance_status)
            except Exception as exception:
                _LOGGER.exception(exception)
                raise UpdateFailed() from exception
        return self.data