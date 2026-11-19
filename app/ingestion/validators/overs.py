
from decimal import Decimal, InvalidOperation


def overs_to_balls(overs):
    """
    Convert cricket over notation to legal balls.

    Examples:
        20   -> 120
        9.2  -> 56
        9.5  -> 59
        5.3  -> 33

    Reject invalid ball components such as 9.7.
    """
    if isinstance(overs, bool) or overs is None:
        raise ValueError("Overs must be a valid number.")

    try:
        value = Decimal(str(overs))
    except (InvalidOperation, ValueError):
        raise ValueError(f"Invalid overs value: {overs}")

    if not value.is_finite() or value < 0:
        raise ValueError(f"Invalid overs value: {overs}")

    whole_overs = int(value)
    fractional_part = value - whole_overs

    # Cricket notation permits only 0-5 balls after the decimal.
    fractional_text = format(fractional_part, "f")

    if fractional_text not in ("0", "0.0", "0.1", "0.2", "0.3", "0.4", "0.5"):
        raise ValueError(f"Invalid cricket over notation: {overs}")

    balls = int(fractional_part * 10)

    return whole_overs * 6 + balls
