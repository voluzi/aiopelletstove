"""Register definitions and pure encoding helpers."""

import math
from dataclasses import dataclass
from typing import Literal

from .exceptions import (
    PelletStoveReadOnlyError,
    PelletStoveResponseError,
    PelletStoveValueError,
)
from .models import FanRegulation

Value = int | float | bool
Memory = Literal["ram", "eep"]


@dataclass(frozen=True)
class Register:
    name: str
    memory: Memory
    reg_id: int
    category: int = 2
    fmt: type[int] | type[float] | type[bool] = int
    read_only: bool = False
    minimum: int | None = None
    maximum: int | None = None
    scale: float = 1.0
    offset: int = 0
    high_byte_reg_id: int | None = None


AIR_TEMPERATURE = Register(
    "air_temperature", "ram", 1, fmt=float, read_only=True, scale=0.5
)
FLUE_TEMPERATURE = Register("flue_temperature", "ram", 2, read_only=True, offset=30)
POWER_STATE = Register("power_state", "ram", 33, read_only=True)
CURRENT_POWER = Register("current_power", "ram", 52, read_only=True)
FAN_SPEED = Register("fan_speed", "ram", 55, read_only=True, scale=10, offset=250)
TARGET_TEMPERATURE = Register("target_temperature", "eep", 125, minimum=7, maximum=40)
POWER_LEVEL = Register("power_level", "eep", 127, minimum=1, maximum=5)
LAST_ALARM = Register("last_alarm", "eep", 224, category=5, read_only=True)
TOTAL_HOURS = Register(
    "total_hours", "eep", 234, category=5, read_only=True, high_byte_reg_id=235
)
PARTIAL_HOURS = Register(
    "partial_hours", "eep", 236, category=5, read_only=True, high_byte_reg_id=237
)
IGNITION_COUNT = Register(
    "ignition_count", "eep", 238, category=5, read_only=True, high_byte_reg_id=239
)
STANDBY_MODE = Register("standby_mode", "eep", 77, category=11, fmt=bool)
BUZZER = Register("buzzer", "eep", 78, category=11, fmt=bool)
ENABLE_FAN = Register("enable_fan", "eep", 80, category=11, fmt=bool)
FAN_REGULATION = Register(
    "fan_regulation", "eep", 126, category=11, minimum=0, maximum=102
)
COMMON_REGISTERS = (
    AIR_TEMPERATURE,
    FLUE_TEMPERATURE,
    POWER_STATE,
    CURRENT_POWER,
    FAN_SPEED,
    TARGET_TEMPERATURE,
    POWER_LEVEL,
)
PREFERENCE_REGISTERS = (STANDBY_MODE, BUZZER, ENABLE_FAN, FAN_REGULATION)
DIAGNOSTIC_REGISTERS = (LAST_ALARM, TOTAL_HOURS, PARTIAL_HOURS, IGNITION_COUNT)
REGISTERS = COMMON_REGISTERS + PREFERENCE_REGISTERS + DIAGNOSTIC_REGISTERS


def decode(reg: Register, raw: int) -> Value:
    if reg.fmt is bool:
        if raw not in (0, 1):
            raise PelletStoveResponseError(f"Invalid boolean for {reg.name}")
        return bool(raw)
    value = raw * reg.scale + reg.offset
    return round(value, 1) if reg.fmt is float else int(value)


def encode(reg: Register, value: Value) -> int:
    if reg.read_only:
        raise PelletStoveReadOnlyError(f"{reg.name} is read-only")
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise PelletStoveValueError(f"Invalid value for {reg.name}")
    if reg.minimum is not None and value < reg.minimum:
        raise PelletStoveValueError(f"{reg.name} minimum is {reg.minimum}")
    if reg.maximum is not None and value > reg.maximum:
        raise PelletStoveValueError(f"{reg.name} maximum is {reg.maximum}")
    if reg.fmt is bool and value not in (0, 1):
        raise PelletStoveValueError(f"{reg.name} requires a boolean")
    raw = (value - reg.offset) / reg.scale
    if not raw.is_integer() or not 0 <= raw <= 255:
        raise PelletStoveValueError(f"Value cannot be encoded for {reg.name}")
    result = int(raw)
    if reg == FAN_REGULATION:
        try:
            unpack_fans(result)
        except PelletStoveResponseError as err:
            raise PelletStoveValueError("Invalid packed fan value") from err
    return result


def combine_bytes(low: int, high: int) -> int:
    if not (0 <= low <= 255 and 0 <= high <= 255):
        raise PelletStoveResponseError("Invalid counter byte")
    return (high << 8) | low


def unpack_fans(raw: int) -> tuple[FanRegulation, FanRegulation]:
    options = tuple(FanRegulation)
    low, high = raw % 16, raw // 16
    if not (0 <= low < len(options) and 0 <= high < len(options)):
        raise PelletStoveResponseError("Invalid packed fan regulation")
    return options[low], options[high]


def pack_fans(fan2: FanRegulation, fan3: FanRegulation) -> int:
    options = tuple(FanRegulation)
    return options.index(fan2) + 16 * options.index(fan3)
