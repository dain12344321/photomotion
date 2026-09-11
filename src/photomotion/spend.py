"""Spend cap: live I2V is opt-in and fail-closed."""

from photomotion.constants import (
    DEFAULT_SPEND_CAP,
    HARD_SPEND_CAP,
    I2V_DURATION_S,
    I2V_IMAGE_INPUT_USD,
    I2V_PRICE_PER_SEC_1080P,
)


class SpendBlocked(RuntimeError):
    pass


def estimate_clip_usd(duration_s: float = I2V_DURATION_S) -> float:
    return round(I2V_PRICE_PER_SEC_1080P * float(duration_s) + I2V_IMAGE_INPUT_USD, 4)


def estimate_job_usd(n_i2v: int, duration_s: float = I2V_DURATION_S) -> float:
    return round(n_i2v * estimate_clip_usd(duration_s), 4)


def assert_live_allowed(
    *,
    dry_run: bool,
    confirm_live: bool,
    spend_cap: float,
    estimated_usd: float,
    already_spent: float = 0.0,
) -> None:
    if dry_run:
        raise SpendBlocked("dry-run: refusing live video API")
    if not confirm_live:
        raise SpendBlocked("live I2V requires explicit confirm")
    cap = min(float(spend_cap), HARD_SPEND_CAP)
    if cap <= 0:
        raise SpendBlocked("spend cap is zero")
    if already_spent + estimated_usd > cap + 1e-9:
        raise SpendBlocked(
            f"estimated ${already_spent + estimated_usd:.2f} exceeds cap ${cap:.2f}"
        )


def clamp_cap(spend_cap: float | None) -> float:
    if spend_cap is None:
        return DEFAULT_SPEND_CAP
    return max(0.0, min(float(spend_cap), HARD_SPEND_CAP))
