"""Immutable decoded stove state."""

from dataclasses import dataclass
from enum import IntEnum, StrEnum


class PowerState(IntEnum):
    OFF = 0
    AWAITING_FLAME_1 = 1
    AWAITING_FLAME_2 = 2
    LIGHTING = 3
    RUNNING = 4
    ASHPAN_CLEANING = 5
    FINAL_CLEANING = 6
    STANDBY = 7
    ALARM = 8
    ALARM_MEMORY = 9

    @property
    def is_on(self) -> bool:
        return self in ON_STATES

    @property
    def label(self) -> str:
        return POWER_STATE_LABELS[self]


ON_STATES = frozenset(
    {
        PowerState.AWAITING_FLAME_1,
        PowerState.AWAITING_FLAME_2,
        PowerState.LIGHTING,
        PowerState.RUNNING,
        PowerState.ASHPAN_CLEANING,
    }
)
POWER_STATE_LABELS = {
    PowerState.OFF: "off",
    PowerState.AWAITING_FLAME_1: "awaiting_flame",
    PowerState.AWAITING_FLAME_2: "awaiting_flame",
    PowerState.LIGHTING: "lighting",
    PowerState.RUNNING: "on",
    PowerState.ASHPAN_CLEANING: "on",
    PowerState.FINAL_CLEANING: "final_cleaning",
    PowerState.STANDBY: "standby",
    PowerState.ALARM: "alarm",
    PowerState.ALARM_MEMORY: "alarm_memory",
}


class FanRegulation(StrEnum):
    OFF = "off"
    LEVEL_1 = "1"
    LEVEL_2 = "2"
    LEVEL_3 = "3"
    LEVEL_4 = "4"
    LEVEL_5 = "5"
    AUTO = "auto"


@dataclass(frozen=True)
class StoveState:
    air_temperature: float
    flue_temperature: int
    power_state: PowerState
    current_power: int
    fan_speed: int
    target_temperature: int
    power_level: int
    standby_mode: bool
    buzzer: bool
    enable_fan: bool
    fan2_regulation: FanRegulation
    fan3_regulation: FanRegulation
    last_alarm: int | None = None
    total_hours: int | None = None
    partial_hours: int | None = None
    ignition_count: int | None = None
