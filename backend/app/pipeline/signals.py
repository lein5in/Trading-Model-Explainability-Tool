import math

PROBABILITY_THRESHOLD = 0.5


def output_to_signal(value, signal_type: str, dead_zone: float):
    if value is None:
        return None
    number = float(value)
    if math.isnan(number):
        return None
    if signal_type == "discrete":
        return 1 if number >= PROBABILITY_THRESHOLD else -1
    if number > dead_zone:
        return 1
    if number < -dead_zone:
        return -1
    return 0


def outputs_to_signals(outputs, signal_type: str, dead_zone: float) -> list:
    return [output_to_signal(value, signal_type, dead_zone) for value in outputs]


def signal_rule(signal_type: str, explained_output: str, dead_zone: float) -> dict:
    if signal_type == "discrete":
        return {
            "rule": f"{explained_output} >= {PROBABILITY_THRESHOLD:.2f} gives long, otherwise short",
            "threshold": PROBABILITY_THRESHOLD,
        }
    if dead_zone == 0:
        return {"rule": "prediction > 0 gives long, < 0 gives short, exactly 0 stays flat", "threshold": 0.0}
    return {
        "rule": f"prediction > {dead_zone:g} gives long, < -{dead_zone:g} gives short, otherwise flat",
        "threshold": dead_zone,
    }
