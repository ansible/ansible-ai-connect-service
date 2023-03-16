from django.conf import settings
from opensearchpy import OpenSearch, RequestsHttpConnection
from sentence_transformers import SentenceTransformer

# TODO: use credentials depending on whether or not we have production ElasticSearch settings
client = OpenSearch(
    hosts=[
        {'host': settings.ANSIBLE_AI_SEARCH['HOST'], 'port': settings.ANSIBLE_AI_SEARCH['PORT']}
    ],
    use_ssl=settings.ANSIBLE_AI_SEARCH['USE_SSL'],
    verify_certs=settings.ANSIBLE_AI_SEARCH['VERIFY_CERTS'],
    connection_class=RequestsHttpConnection,
    pool_maxsize=20,
)


model = SentenceTransformer(f"sentence-transformers/{settings.ANSIBLE_AI_SEARCH['MODEL']}")


def generate_query(encoded):
    return {
        'size': 3,
        'query': {
            'knn': {'output_body_vector': {'vector': encoded.tolist(), 'k': 1}},
        },
        'fields': ['source', 'type', 'license', 'output_body', 'repo_url'],
    }


def search(suggestion):
    encoded = model.encode(suggestion)
    query = generate_query(encoded)
    results = client.search(index=settings.ANSIBLE_AI_SEARCH['INDEX'], body=query, _source=False)
    return results['hits']['hits']
