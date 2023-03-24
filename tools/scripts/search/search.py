import argparse
import json
import os

import boto3
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection
from sentence_transformers import SentenceTransformer

host = os.getenv('OS_HOST')
region = os.getenv('AWS_REGION')

credentials = boto3.Session().get_credentials()
auth = AWSV4SignerAuth(credentials, region, 'es')

# create an opensearch client and use the request-signer
client = OpenSearch(
    hosts=[{'host': host, 'port': 443}],
    http_auth=auth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    pool_maxsize=20,
)


def generate_search(encoded_output):
    return {
        "size": 3,
        "query": {
            "knn": {"output_body_vector": {"vector": encoded_output.tolist(), "k": 1}},
        },
        "fields": ['repo_name', 'repo_url', 'path', 'license', 'data_source', 'type'],
        "_source": False,
    }


def main():
    model = SentenceTransformer(f'sentence-transformers/{args.model}')
    encoded_output = model.encode(args.output)

    # NOTE: we need to fix some of the result set data types:
    # "license": "license (MIT)",
    # "license": "['MIT']",
    # "license": "license (BSD, MIT)",

    query = generate_search(encoded_output)
    results = client.search(index=args.index, body=query, _source=False)
    res = json.dumps(results['hits']['hits'])
    print(res)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generating bulk load file')
    parser.add_argument('--model', default='all-mpnet-base-v2', help='NLP model to use')
    parser.add_argument('--index', required=True, help='Elasticsearch index')
    parser.add_argument('--output', required=True, help='Recommendation to search for')
    args = parser.parse_args()
    main()
