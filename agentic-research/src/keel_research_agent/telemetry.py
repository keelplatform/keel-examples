"""OTel SDK wiring — OTLP exporter to the local collector (Jaeger / SigNoz /
your own OTel collector). One small function, configured by environment.

Production deployments configure OTel via env vars (``OTEL_EXPORTER_OTLP_ENDPOINT``,
``OTEL_SERVICE_NAME``, etc.); this module does that explicitly so the demo is
turnkey from ``docker compose up`` to traces-in-Jaeger.
"""

from __future__ import annotations

import os

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def setup_otel() -> None:
    """Configure OTel SDK to export to the OTLP collector.

    Env vars (with sensible defaults for ``docker compose up``):
    - ``OTEL_EXPORTER_OTLP_ENDPOINT`` — default ``http://jaeger:4317``
    - ``OTEL_SERVICE_NAME`` — default ``keel-research-agent``
    """
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")
    service_name = os.getenv("OTEL_SERVICE_NAME", "keel-research-agent")
    resource = Resource.create({"service.name": service_name})

    # Tracing — batched OTLP/gRPC export.
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
    )
    trace.set_tracer_provider(tracer_provider)

    # Metrics — periodic OTLP export.
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=endpoint, insecure=True),
        export_interval_millis=10_000,
    )
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[metric_reader]))
