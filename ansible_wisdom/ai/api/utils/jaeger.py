import json
import inspect
from opentelemetry.sdk.resources import Resource
from django.conf import settings

# Import exporters
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

# Trace imports
from opentelemetry import trace
from opentelemetry.trace import set_tracer_provider, get_tracer_provider
from opentelemetry.sdk.trace import TracerProvider, sampling
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# ===== GENERAL SETUP =====

DT_API_URL = "https://win89656.live.dynatrace.com/api/v2/otlp"
DT_API_TOKEN = "dt0c01.BDJQZ4B5GF4TVLQNOL22UHLK.GVEBHIVB427YF5MSH2KTSFNNEKCICSLU7IB2GHNINUUQXBMJ3CA4FC7HLJRYGW4X"


merged = dict()
for name in ["dt_metadata_e617c525669e072eebe3d0f08212e8f2.json", "/var/lib/dynatrace/enrichment/dt_metadata.json"]:
  try:
    data = ''
    with open(name) as f:
      data = json.load(f if name.startswith("/var") else open(f.read()))
      merged.update(data)
  except:
    pass

merged.update({
  "service.name": "Ansible Lightspeed", #TODO Replace with the name of your application
  "service.version": "1.0.1", #TODO Replace with the version of your application
})
resource = Resource.create(merged)


# ===== TRACING SETUP =====

tracer_provider = TracerProvider(sampler=sampling.ALWAYS_ON, resource=resource)
trace.set_tracer_provider(tracer_provider)

tracer_provider.add_span_processor(
  BatchSpanProcessor(
    OTLPSpanExporter(
      endpoint = DT_API_URL + "/v1/traces",
      headers = {
        "Authorization": "Api-Token " + DT_API_TOKEN
      }
    )
  )
)

tracer = get_tracer_provider().get_tracer("my-tracer")



#tracing method
def distributed_tracing_method(name, description, file, method, span_ctx):
    inner_span_ctx = None
    if settings.ENABLE_DISTRIBUTED_TRACING:
        with tracer.start_as_current_span(name=name, context=span_ctx) as span:
            span.set_attribute('File', file)
            span.set_attribute('Method', method)
            span.set_attribute('Description', description)
            inner_span_ctx = trace.set_span_in_context(trace.get_current_span())

    return inner_span_ctx





#wrapper method
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
