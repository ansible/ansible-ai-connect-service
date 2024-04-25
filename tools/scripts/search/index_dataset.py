#  Copyright Red Hat
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import argparse
import json
import os

import boto3
import tqdm
from datasets import load_from_disk
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection
from opensearchpy.helpers import streaming_bulk
from sentence_transformers import SentenceTransformer

host = os.getenv('OS_HOST')
region = os.getenv('AWS_REGION')

credentials = boto3.Session().get_credentials()
auth = AWSV4SignerAuth(credentials, region, 'es')

INDEX = {
    "settings": {"number_of_shards": 2, "index.knn": "true", "index.refresh_interval": "-1"},
    "mappings": {
        "properties": {
            "repo_name": {"type": "text"},
            "repo_url": {"type": "text"},
            "data_source": {"type": "byte"},
            "type": {"type": "byte"},
            "path": {"type": "text"},
            "output_body": {"type": "text"},
            "license": {"type": "text"},
            "sample_type": {"type": "byte"},
            "output_body_vector": {
                "type": "knn_vector",
                # dimension is model-specific
                "dimension": 384,
                "index": "true",
                # method is model-specific
                "method": {"name": "hnsw", "space_type": "innerproduct", "engine": "nmslib"},
            },
        }
    },
}

INDEX_ENABLE = {"settings": {"index.refresh_interval": "1s"}}

client = OpenSearch(
    hosts=[{'host': host, 'port': 443}],
    http_auth=auth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    pool_maxsize=20,
)


def main():
    model = SentenceTransformer(f'sentence-transformers/{args.model}')
    print(f"loading dataset {args.input}")
    df = load_from_disk(args.input)

    print(f"encoding dataset {args.input}")
    encoded_df = df.map(
        lambda x: {"output_body_vector": model.encode(x['output_body'], normalize_embeddings=True)},
        batched=True,
    )

    print(f"creating index {args.index}")
    response = client.indices.create(index=args.index, body=INDEX)
    print(json.dumps(response))

    print(f"indexing dataset {args.input}")
    num_docs = len(encoded_df)
    print(f"found {num_docs} records")
    print(f"loading index {args.index}")

    progress = tqdm.tqdm(unit="docs", total=num_docs)

    # parallel_bulk overwhelmed the endpoint
    for ok, action in streaming_bulk(
        client=client, index=args.index, actions=encoded_df, chunk_size=1000
    ):
        progress.update(1)

    print(f'updating index: {args.index}')
    response = client.indices.put_settings(index=args.index, body=INDEX_ENABLE)
    print(json.dumps(response))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Bulk load the Elasticsearch index')
    parser.add_argument('--input', required=True, help='path to the dataset files')
    parser.add_argument('--model', default='all-mpnet-base-v2', help='NLP model to use')
    parser.add_argument('--index', required=True, help='Elasticsearch index')
    args = parser.parse_args()
    main()
