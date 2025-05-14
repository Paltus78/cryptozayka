"""OpenTelemetry setup – single entry to init tracing & metrics exporters.

* Uses OTLP/gRPC exporter (endpoint via OTEL_EXPORTER_OTLP_ENDPOINT)
* If env var absent, falls back to console exporter.
* Automatically instruments FastAPI, asyncpg, aiohttp, logging.
"""
from __future__ import annotations

import os
from contextlib import suppress

from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    OTLPSpanExporter,
)
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor

_initialized = False

def init_otel(app=None):
    global _initialized
    if _initialized:
        return
    _initialized = True

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    exporter = (
        OTLPSpanExporter(endpoint=endpoint, insecure=True)
        if endpoint
        else ConsoleSpanExporter()
    )

    provider = TracerProvider(
        resource=Resource.create({SERVICE_NAME: "cryptozayka"})
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Instrument libs
    if app is not None:
        FastAPIInstrumentor().instrument_app(app)
    else:
        FastAPIInstrumentor().instrument()

    with suppress(Exception):
        AsyncPGInstrumentor().instrument()
    with suppress(Exception):
        AioHttpClientInstrumentor().instrument()
    LoggingInstrumentor().instrument(set_logging_format=True)
