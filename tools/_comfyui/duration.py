"""Duration helpers for bundled ComfyUI video workflows."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any


WAN_FRAME_BUCKETS = (17, 33, 49, 65, 81)


def wan_i2v_duration_seconds(num_frames: int) -> float:
    """Return the user-facing Wan I2V duration represented by a frame bucket."""

    return (num_frames - 1) / 16


def infinitetalk_duration_seconds(num_frames: int, segment_count: int) -> float:
    """Return rendered duration for the overlapping InfiniteTalk segment chain."""

    overlap = 9
    rendered_frames = num_frames + max(0, segment_count - 1) * (num_frames - overlap)
    return rendered_frames / 25


def resolve_frame_bucket(
    inputs: dict[str, Any],
    *,
    default_frames: int,
    duration_for_frames: Callable[[int], float],
    label: str,
    buckets: Iterable[int] = WAN_FRAME_BUCKETS,
) -> tuple[int, float | None, float]:
    """Resolve mutually exclusive seconds/frames inputs to a legal frame bucket."""

    frame_buckets = tuple(int(value) for value in buckets)
    requested_duration = inputs.get("duration_seconds")
    requested_frames = inputs.get("num_frames")
    if requested_duration is not None and requested_frames is not None:
        raise ValueError(f"{label} accepts duration_seconds or num_frames, not both")

    if requested_duration is None:
        frames = int(requested_frames if requested_frames is not None else default_frames)
        if frames not in frame_buckets:
            choices = ", ".join(str(value) for value in frame_buckets)
            raise ValueError(f"{label} num_frames must be one of: {choices}")
        return frames, None, duration_for_frames(frames)

    requested = float(requested_duration)
    if requested <= 0:
        raise ValueError("duration_seconds must be greater than 0")
    options = [(frames, duration_for_frames(frames)) for frames in frame_buckets]
    minimum = min(duration for _, duration in options)
    maximum = max(duration for _, duration in options)
    if requested < minimum or requested > maximum:
        raise ValueError(
            f"{label} duration_seconds must be between {minimum:.2f} and {maximum:.2f}"
        )
    frames, selected = min(options, key=lambda option: abs(option[1] - requested))
    return frames, requested, selected
