class PricingError(Exception):
    """Base class for deterministic pricing-evaluator failures."""


class MissingSlotError(PricingError):
    def __init__(self, slot: str):
        super().__init__(f"Missing required slot: {slot!r}")
        self.slot = slot


class InvalidSlotValueError(PricingError):
    def __init__(self, slot: str, value, reason: str):
        super().__init__(f"Invalid value for slot {slot!r}: {value!r} ({reason})")
        self.slot = slot
        self.value = value
        self.reason = reason


class RateNotFoundError(PricingError):
    def __init__(self, slots: dict):
        super().__init__(f"No rate_table entry matches slots: {slots!r}")
        self.slots = slots
