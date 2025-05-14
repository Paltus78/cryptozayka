"""
Lightweight metrics shim for Cryptozayka.
Works with OpenTelemetry if it is installed; otherwise falls back to no-op stubs.
"""
from typing import Tuple

try:
    # optional dependency
    from opentelemetry.metrics import get_meter_provider, set_meter_provider
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource

    _resource = Resource.create({"service.name": "cryptozayka"})
    _reader = PeriodicExportingMetricReader(export_interval_millis=60_000)
    set_meter_provider(MeterProvider(metric_readers=[_reader],
                                     resource=_resource))
    _meter = get_meter_provider().get_meter("cryptozayka")

    QUEUE_SIZE = _meter.create_up_down_counter(
        name="queue_size",
        description="Current size of processing queue",
        unit="tasks",
    )
    GPT_SPENT = _meter.create_counter(
        name="gpt_tokens_spent",
        description="Total GPT tokens spent",
        unit="tokens",
    )

except Exception:       # OpenTelemetry не установлен ─> no-op
    class _Dummy:
        def add(self, *a, **kw): ...
        def inc(self, *a, **kw): ...
        def set(self, *a, **kw): ...
        def record(self, *a, **kw): ...

    QUEUE_SIZE = GPT_SPENT = _Dummy()

# ───────────────────────────────────────────────────────────────
def init_otel() -> Tuple[object, object]:
    """
    Обертка, ожидаемая старым кодом.
    Возвращает (QUEUE_SIZE, GPT_SPENT) — счётчики, созданные выше.
    """
    return QUEUE_SIZE, GPT_SPENT
# ───────────────────────────────────────────────────────────────
