#from prometheus_client import Counter, Gauge, Info, push_to_gateway, CollectorRegistry
#import uwsgi

# Define custom metrics
# requests_total = Counter('django_requests_total', 'Total number of requests')
# response_time = Gauge('django_response_time', 'Time to respond to a request')

# def collect_metrics():
#     # Collect metrics from uWSGI server
#     stats = uwsgi.stats()
#     total_requests = stats['total_requests']
#     avg_response_time = stats['avg_response_time']

#     # Update Prometheus metrics
#     requests_total.inc(total_requests)
#     response_time.set(avg_response_time)
from prometheus_client import CollectorRegistry
from prometheus_client import multiprocess
from prometheus_client.exposition import start_http_server


registry = CollectorRegistry()
# Set up the multiprocess mode and specify the port number
multiprocess.MultiProcessCollector(registry)
start_http_server(8001, registry=registry)
