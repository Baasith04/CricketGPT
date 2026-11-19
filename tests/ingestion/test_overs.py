
import pytest

from app.ingestion.validators.overs import overs_to_balls


@pytest.mark.parametrize(
    "overs, expected",
    [
        (20, 120),
        (10, 60),
        (9.2, 56),
        (9.5, 59),
        (5.3, 33),
        (0, 0),
        ("9.2", 56),
        ("20.0", 120),
    ],
)
def test_overs_to_balls(overs, expected):
    assert overs_to_balls(overs) == expected


@pytest.mark.parametrize(
    "overs",
    [
        -1,
        9.7,
        9.6,
        9.25,
        "invalid",
        None,
        True,
    ],
)
def test_invalid_overs(overs):
    with pytest.raises(ValueError):
        overs_to_balls(overs)
