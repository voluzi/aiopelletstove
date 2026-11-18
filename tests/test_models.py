import pytest

from aiopelletstove import PowerState


@pytest.mark.parametrize(
    "state,label",
    [
        (PowerState.OFF, "off"),
        (PowerState.LIGHTING, "lighting"),
        (PowerState.AWAITING_FLAME_1, "awaiting_flame"),
        (PowerState.AWAITING_FLAME_2, "awaiting_flame"),
        (PowerState.RUNNING, "on"),
        (PowerState.ASHPAN_CLEANING, "on"),
        (PowerState.FINAL_CLEANING, "final_cleaning"),
        (PowerState.STANDBY, "standby"),
        (PowerState.ALARM, "alarm"),
        (PowerState.ALARM_MEMORY, "alarm_memory"),
    ],
)
def test_power_state_labels(state, label):
    assert state.label == label
