"""Generate a synthetic onboarding dataset with the same schema as the
private transaction-level extract.

Why this exists
---------------
The real extracts are confidential and cannot be published. This generator
produces a fully artificial dataset - no real records, identifiers or
customers - so that anyone can run the complete pipeline end-to-end::

    python -m src.data_generation.generate_synthetic_data --rows 25000

Distributions are loosely calibrated to *aggregate* patterns observed during
profiling (outcome mix, platform cancellation gaps, stage drop-off shares,
journey duration), so the demo charts look realistic. They are illustrative,
not statistically identical to the private data.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import SYNTHETIC_ONBOARDING_FILE

# --------------------------------------------------------------------------- #
# Calibration constants (aggregate patterns only)
# --------------------------------------------------------------------------- #
SOURCE_MIX = {
    "createForRequest": 0.1909,
    "application-update-by-agent": 0.1251,
    "finishTransaction": 0.6840,
}

# Platform shares for completed-flow records.
FINISH_PLATFORMS = {
    "android": 0.796,
    "ios": 0.121,
    "windows": 0.052,
    "macos": 0.007,
    "missing": 0.021,
    "unknown": 0.003,
}

# Probability that a completed-flow journey is cancelled by the user.
CANCEL_RATE = {
    "android": 0.284,
    "ios": 0.106,
    "windows": 0.275,
    "macos": 0.184,
    "missing": 0.204,
    "unknown": 0.222,
}

# Share of cancellations whose last stage was document verification.
DOC_STAGE_CANCEL_SHARE = {
    "android": 0.625,
    "ios": 0.168,
    "windows": 0.441,
    "macos": 0.465,
    "missing": 0.556,
    "unknown": 0.604,
}

# Remaining cancellations are spread across these stages.
OTHER_CANCEL_STAGES = {
    "id_card": 0.718,
    "form": 0.129,
    "selfie": 0.115,
    "country": 0.038,
}

ERROR_RATE = 0.0068
NEEDS_REVIEW_RATE = 0.0004
AUTO_DECLINE_RATE_AMONG_COMPLETED = 0.066
MANUAL_APPROVAL_SHARE = 0.9068

DECLINE_STAGES = {
    "none": 0.283,
    "face_match": 0.261,
    "selfie": 0.190,
    "id_card": 0.124,
    "form": 0.074,
    "other": 0.068,
}

# Relative activity by hour of day (index = hour).
HOURLY_WEIGHTS = np.array([
    5.0, 3.2, 1.8, 1.1, 0.9, 1.2, 2.3, 4.6, 6.5, 8.6, 10.6, 11.5,
    11.4, 11.3, 11.1, 11.1, 11.2, 10.1, 11.1, 12.1, 12.8, 11.8, 10.9, 9.1,
])

MODULE_TEMPLATES = {
    "geo": "module_{code}_ip_geolocation_api",
    "doc": "module_{code}_document_verification_form",
    "id_card": "module_{code}_id_card_validation",
    "selfie": "module_{code}_selfie_validation",
    "face_match": "module_{code}_face_match_api",
    "form": "module_{code}_form",
    "country": "module_countryPicker",
    "other": "module_{code}_genericApiV1",
}

SDK_VERSIONS = {
    "Web SDK: 9.12.0 Mobile SDK: 2.3.4": 0.74,
    "Web SDK: 9.17.0": 0.25,
    "Web SDK: 9.12.0 Mobile SDK: 2.0.1": 0.005,
    "Web SDK: 9.12.0 Mobile SDK: 2.0.0": 0.005,
}

# Median journey duration (seconds) by status.
MEDIAN_SECONDS = {
    "auto_approved": 183.0,
    "auto_declined": 156.0,
    "user_cancelled": 57.0,
    "error": 23.0,
    "needs_review": 213.0,
}


def _choice(rng, options: dict, size: int):
    keys = list(options)
    probs = np.array(list(options.values()), dtype=float)
    return rng.choice(keys, size=size, p=probs / probs.sum())


def _format_timestamp(ts: pd.Timestamp) -> str:
    """Format like the source export, e.g. 'Mar 24, 2026, 5:05 PM'."""

    hour12 = ts.hour % 12 or 12
    meridiem = "AM" if ts.hour < 12 else "PM"
    return f"{ts:%b %d, %Y}, {hour12}:{ts.minute:02d} {meridiem}"


def _module_code(rng, index: int) -> str:
    alphabet = list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
    return "".join(rng.choice(alphabet, size=6)) + str(index % 3)


def _stage_for_status(rng, row_status, platform) -> str | None:
    """Pick the last executed stage consistent with the outcome."""

    if row_status in ("auto_approved",):
        return "geo"

    if row_status == "user_cancelled":
        if rng.random() < DOC_STAGE_CANCEL_SHARE.get(platform, 0.55):
            return "doc"
        return str(_choice(rng, OTHER_CANCEL_STAGES, 1)[0])

    if row_status == "auto_declined":
        stage = str(_choice(rng, DECLINE_STAGES, 1)[0])
        return None if stage == "none" else stage

    if row_status in ("error", "needs_review"):
        return str(rng.choice(["id_card", "selfie", "geo", "form"]))

    return None


def generate_onboarding_data(rows: int = 25_000, seed: int = 42) -> pd.DataFrame:
    """Create the synthetic dataset."""

    rng = np.random.default_rng(seed)

    source = _choice(rng, SOURCE_MIX, rows)
    status = np.empty(rows, dtype=object)
    platform = np.empty(rows, dtype=object)

    # ---- outcome and platform per source --------------------------------
    for i, src in enumerate(source):
        if src == "createForRequest":
            status[i] = "started"
            platform[i] = str(_choice(
                rng,
                {"android": 0.665, "ios": 0.125, "missing": 0.207,
                 "windows": 0.002, "web": 0.002, "macos": 0.0},
                1,
            )[0])

        elif src == "application-update-by-agent":
            status[i] = (
                "manually_approved"
                if rng.random() < MANUAL_APPROVAL_SHARE
                else "manually_declined"
            )
            platform[i] = "missing"

        else:
            plat = str(_choice(rng, FINISH_PLATFORMS, 1)[0])
            platform[i] = plat
            draw = rng.random()

            if draw < ERROR_RATE:
                status[i] = "error"
            elif draw < ERROR_RATE + NEEDS_REVIEW_RATE:
                status[i] = "needs_review"
            elif rng.random() < CANCEL_RATE[plat]:
                status[i] = "user_cancelled"
            elif rng.random() < AUTO_DECLINE_RATE_AMONG_COMPLETED:
                status[i] = "auto_declined"
            else:
                status[i] = "auto_approved"

    # ---- timestamps ------------------------------------------------------
    days = pd.date_range("2026-03-01", "2026-03-31", freq="D")
    day_index = rng.integers(0, len(days), size=rows)
    hours = rng.choice(24, size=rows, p=HOURLY_WEIGHTS / HOURLY_WEIGHTS.sum())
    minutes = rng.integers(0, 60, size=rows)

    created = (
        days[day_index]
        + pd.to_timedelta(hours, unit="h")
        + pd.to_timedelta(minutes, unit="m")
    )
    event_time = created - pd.to_timedelta(rng.integers(0, 6, size=rows), unit="m")
    started_at = event_time - pd.to_timedelta(
        rng.choice([0, 0, 0, 1, 2, 5, 30, 240], size=rows), unit="m"
    )

    # ---- stage / module --------------------------------------------------
    last_module = np.empty(rows, dtype=object)
    for i in range(rows):
        stage = _stage_for_status(rng, status[i], platform[i])
        last_module[i] = (
            None
            if stage is None
            else MODULE_TEMPLATES[stage].format(code=_module_code(rng, i))
        )

    # ---- journey duration (milliseconds, stored with thousands sep) -----
    time_spent = np.full(rows, np.nan)
    for i in range(rows):
        if source[i] != "finishTransaction":
            continue
        median = MEDIAN_SECONDS.get(status[i], 150.0)
        seconds = rng.lognormal(mean=np.log(median), sigma=0.9)
        # ~0.1% implausibly long journeys to exercise outlier handling.
        if rng.random() < 0.001:
            seconds = rng.uniform(5_000, 90_000)
        time_spent[i] = round(seconds * 1000)

    time_spent_text = [
        None if np.isnan(value) else f"{int(value):,}" for value in time_spent
    ]

    # ---- SDK, updates ----------------------------------------------------
    sdk = np.where(
        source == "finishTransaction",
        _choice(rng, SDK_VERSIONS, rows),
        None,
    )

    base_updates = np.where(
        np.isin(status, ["auto_declined", "manually_declined"]), 7,
        np.where(status == "user_cancelled", 6, 4),
    )
    updates = base_updates + rng.poisson(1.5, size=rows)
    updates_text = updates.astype(object)
    # One value stored with a thousands separator (mirrors a real quirk).
    updates_text[rng.integers(0, rows)] = "1,599"

    index = np.arange(1, rows + 1)

    df = pd.DataFrame({
        "id": [f"syn-id-{n:07d}" for n in index],
        "app_id": rng.choice(["syn-app-001", "syn-app-002"], size=rows),
        "transaction_id": [f"SYN-TXN-{n:07d}" for n in index],
        "workflow_id": rng.choice(["syn-wf-01", "syn-wf-02"], size=rows),
        "status": status,
        "source": source,
        "country": np.nan,
        "created_at": [_format_timestamp(ts) for ts in created],
        "event_time": [_format_timestamp(ts) for ts in event_time],
        "last_executed_module": last_module,
        "platform": platform,
        "sdk_version": sdk,
        "latest_condition": np.nan,
        "error": np.nan,
        "time_spent": time_spent_text,
        "transaction_start_timestamp": [
            _format_timestamp(ts) for ts in started_at
        ],
        "failure_reason": np.nan,
        "failure_condition": np.nan,
        "review_decision_reasons": np.nan,
        "total_transaction_updates": updates_text,
    })

    return df


def main(rows: int = 25_000, seed: int = 42, output: Path | None = None):
    output = Path(output) if output else SYNTHETIC_ONBOARDING_FILE
    output.parent.mkdir(parents=True, exist_ok=True)

    df = generate_onboarding_data(rows=rows, seed=seed)
    df.to_csv(output, index=False)

    print(f"Generated {len(df):,} synthetic onboarding records.")
    print(f"Saved to: {output}")
    print("This dataset is entirely artificial; it contains no real data.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=25_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    main(rows=args.rows, seed=args.seed, output=args.output)
