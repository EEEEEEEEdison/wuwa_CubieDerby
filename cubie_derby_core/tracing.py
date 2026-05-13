from __future__ import annotations

from typing import Protocol, TypeAlias


class TraceSink(Protocol):
    def write_line(self, message: str) -> None: ...


TraceContext: TypeAlias = bool | TraceSink
