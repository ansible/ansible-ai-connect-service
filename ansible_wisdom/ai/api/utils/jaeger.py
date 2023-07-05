from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

trace.set_tracer_provider(TracerProvider(resource=Resource.create({SERVICE_NAME: "request"})))

# create a JaegerExporter
jaeger_exporter = JaegerExporter(
    # configure agent
    agent_host_name='localhost',
    agent_port=6831,
    # optional: configure also collector
    # collector_endpoint='http://localhost:14268/api/traces?format=jaeger.thrift',
    # username=xxxx, # optional
    # password=xxxx, # optional
    # max_tag_value_length=None # optional
)

# # Create a BatchSpanProcessor and add the exporter to it
span_processor = BatchSpanProcessor(jaeger_exporter)
#
# # add to the tracer
trace.get_tracer_provider().add_span_processor(span_processor)
tracer = trace.get_tracer(__name__)


def enable_tracing(name, file, method, description, span_ctx):
    with tracer.start_as_current_span(name, context=span_ctx) as span:
        span.set_attribute('File', file)
        span.set_attribute('Method', method)
        span.set_attribute('Description', description)
        return trace.set_span_in_context(trace.get_current_span())
