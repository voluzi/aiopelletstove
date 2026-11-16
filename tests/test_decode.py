from dataclasses import replace

import pytest

from aiopelletstove import PelletStoveReadOnlyError, PelletStoveValueError
from aiopelletstove import registers as r
from aiopelletstove.models import FanRegulation
from aiopelletstove.registers import decode, encode, pack_fans, unpack_fans


@pytest.mark.parametrize(
    "reg,raw,expected",
    [
        (r.AIR_TEMPERATURE, 43, 21.5),
        (r.FLUE_TEMPERATURE, 88, 118),
        (r.FAN_SPEED, 61, 860),
        (r.STANDBY_MODE, 1, True),
        (r.BUZZER, 0, False),
        (r.BUZZER, 2, True),
    ],
)
def test_decode_transforms(reg, raw, expected):
    assert decode(reg, raw) == expected


@pytest.mark.parametrize(
    "reg,value",
    [
        (r.TARGET_TEMPERATURE, 6),
        (r.TARGET_TEMPERATURE, 41),
        (r.POWER_LEVEL, 0),
        (r.POWER_LEVEL, 6),
        (r.POWER_LEVEL, 1.5),
        (r.POWER_LEVEL, float("nan")),
        (r.BUZZER, 2),
        (r.FAN_REGULATION, 256),
        (r.FAN_REGULATION, 7),
    ],
)
def test_invalid_write_values(reg, value):
    with pytest.raises(PelletStoveValueError):
        encode(reg, value)


def test_read_only_rejection():
    with pytest.raises(PelletStoveReadOnlyError):
        encode(r.AIR_TEMPERATURE, 20)


def test_inverse_transform():
    register = replace(r.FAN_SPEED, read_only=False)
    assert encode(register, 860) == 61


@pytest.mark.parametrize("fan2", list(FanRegulation))
@pytest.mark.parametrize("fan3", list(FanRegulation))
def test_packed_fans_round_trip(fan2, fan3):
    assert unpack_fans(pack_fans(fan2, fan3)) == (fan2, fan3)
