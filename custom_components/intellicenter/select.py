"""Pentair Intellicenter select entities.

This module provides select entities for pump circuit mode selection
(RPM vs GPM for variable speed/flow pumps).
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyintellicenter import (
    CIRCUIT_ATTR,
    PMPCIRC_TYPE,
    SELECT_ATTR,
    PoolObject,
)

from . import IntelliCenterConfigEntry, PoolEntity
from .coordinator import IntelliCenterCoordinator

_LOGGER = logging.getLogger(__name__)

# Coordinator handles updates via push, so no parallel update limit needed
PARALLEL_UPDATES = 0

# Pump mode options
PUMP_MODE_RPM = "RPM"
PUMP_MODE_GPM = "GPM"
PUMP_MODES = [PUMP_MODE_RPM, PUMP_MODE_GPM]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntelliCenterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Load Pentair select entities based on a config entry."""
    coordinator = entry.runtime_data

    selects: list[PumpModeSelect] = []

    pool_obj: PoolObject
    for pool_obj in coordinator.model:
        # Create pump mode selector for PMPCIRC objects that have SELECT_ATTR
        # This indicates a VSF pump that supports both RPM and GPM modes
        if pool_obj.objtype == PMPCIRC_TYPE and SELECT_ATTR in pool_obj.attribute_keys:
            # Get the associated circuit for naming
            circuit_objnam = pool_obj[CIRCUIT_ATTR]
            circuit = coordinator.model[circuit_objnam] if circuit_objnam else None
            circuit_name = circuit.sname if circuit else circuit_objnam

            selects.append(
                PumpModeSelect(
                    coordinator,
                    pool_obj,
                    circuit_name=circuit_name,
                )
            )

    async_add_entities(selects)


class PumpModeSelect(PoolEntity, SelectEntity):
    """Select entity for pump circuit mode (RPM/GPM)."""

    _attr_icon = "mdi:swap-horizontal"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: IntelliCenterCoordinator,
        pool_object: PoolObject,
        circuit_name: str,
    ) -> None:
        """Initialize the pump mode select entity."""
        super().__init__(coordinator, pool_object)
        self._circuit_name = circuit_name
        self._attr_options = PUMP_MODES

    @property
    def unique_id(self) -> str:
        """Return a unique id for the entity."""
        return f"{self._entry_id}_{self._pool_object.objnam}_{SELECT_ATTR}"

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return f"{self._pool_object.sname} Mode ({self._circuit_name})"

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        value = self._pool_object[SELECT_ATTR]
        if value is not None and str(value) in PUMP_MODES:
            return str(value)
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if option not in PUMP_MODES:
            _LOGGER.warning("Invalid pump mode option: %s", option)
            return

        await self._controller.set_attribute(
            self._pool_object.objnam, SELECT_ATTR, option
        )

    @callback
    def _is_updated(self, updates: dict[str, dict[str, Any]]) -> bool:
        """Check if the entity should be updated based on the changes."""
        if self._pool_object.objnam not in updates:
            return False
        return SELECT_ATTR in updates[self._pool_object.objnam]
