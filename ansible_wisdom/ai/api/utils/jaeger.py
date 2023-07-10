import inspect

from django.conf import settings
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

trace.set_tracer_provider(TracerProvider(resource=Resource.create({SERVICE_NAME: "REQUEST"})))

jaeger_exporter = JaegerExporter(
    agent_host_name='localhost',
    agent_port=6831,
)

span_processor = BatchSpanProcessor(jaeger_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)
tracer = trace.get_tracer(__name__)


def distributed_tracing_method(name, description, file, method, span_ctx):
    if settings.ENABLE_DISTRIBUTED_TRACING:
        with tracer.start_as_current_span(name=name, context=span_ctx) as span:
            span.set_attribute('File', file)
            span.set_attribute('Method', method)
            span.set_attribute('Description', description)
            inner_span_ctx = trace.set_span_in_context(trace.get_current_span())

    return inner_span_ctx


def with_distributed_tracing(name, description, file, method):
    def distributed_tracing_decorator(func):
        def distributed_tracing_wrapper(self, *args, **kwargs):
            inner_span_ctx = None

            if settings.ENABLE_DISTRIBUTED_TRACING:
                with tracer.start_as_current_span(
                    name=name, context=kwargs.get('span_ctx')
                ) as span:
                    span.set_attribute('File', file)
                    span.set_attribute('Method', method)
                    span.set_attribute('Description', description)
                    inner_span_ctx = trace.set_span_in_context(trace.get_current_span())

            if 'inner_span_ctx' in inspect.signature(func).parameters:
                return func(self, *args, **kwargs, inner_span_ctx=inner_span_ctx)
            else:
                return func(self, *args, **kwargs)

        # You can copy more attributes if needed

        return distributed_tracing_wrapper

    return distributed_tracing_decorator
