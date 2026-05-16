from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


FormatOverviewFn = Callable[..., list[str]]


def _slugify_trace_component(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", text.strip().lower())
    return slug.strip("-") or "trace"


def default_trace_log_path(
    config: Any,
    *,
    seed: int | None,
    generated_at: datetime | None = None,
) -> Path:
    if generated_at is None:
        generated_at = datetime.now()
    stage = config.match_type or f"season{config.season}"
    timestamp = generated_at.strftime("%Y%m%d-%H%M%S")
    seed_suffix = f"-seed{seed}" if seed is not None else ""
    filename = (
        f"{timestamp}-s{config.season}-{_slugify_trace_component(stage)}-"
        f"{config.track_length}cells{seed_suffix}.log"
    )
    return Path("logs") / "trace" / filename


def format_trace_metadata_lines(
    config: Any,
    *,
    seed: int | None,
    generated_at: datetime | None,
    format_simulation_overview_lines_fn: FormatOverviewFn,
) -> list[str]:
    if generated_at is None:
        generated_at = datetime.now()
    overview_lines = format_simulation_overview_lines_fn(config, 1, pending=True)
    seed_label = "未固定" if seed is None else str(seed)
    return [
        "=== 日志元信息 ===",
        f"生成时间：{generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"随机种子：{seed_label}",
        *overview_lines,
        "=" * 24,
    ]
