import argparse
import json
import os

import pandas as pd
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer


def generate_search(str):
    model = SentenceTransformer(f'sentence-transformers/{args.model}')
    encoded_output = model.encode(str)

    return {
        "knn": {
            "field": "output_script_vector",
            "query_vector": encoded_output.tolist(),
            "k": 10,
            "num_candidates": 10,
        },
        "fields": ['source', 'type', 'license', 'output_script'],
        "_source": False,
    }


def main():
    client = Elasticsearch(os.getenv('ELASTICSEARCH_URI', 'http://localhost:9200'))

    # NOTE: we need to fix some of the result set data types:
    # "license": "license (MIT)",
    # "license": "['MIT']",
    # "license": "license (BSD, MIT)",

    query = generate_search(args.output)
    results = client.search(
        index=args.index, knn=query["knn"], _source=False, fields=query["fields"]
    )
    res = json.dumps(results['hits']['hits'])
    print(res)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generating bulk load file')
    parser.add_argument('--model', default='all-mpnet-base-v2', help='NLP model to use')
    parser.add_argument('--index', required=True, help='Elasticsearch index')
    parser.add_argument('--output', required=True, help='Recommendation to search for')
    args = parser.parse_args()
    main()
