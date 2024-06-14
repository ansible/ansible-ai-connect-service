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

import time

from django.conf import settings
from opensearchpy import OpenSearch, RequestsHttpConnection
from sentence_transformers import SentenceTransformer

if settings.ANSIBLE_AI_SEARCH["REGION"]:
    import boto3
    from opensearchpy import AWSV4SignerAuth

    credentials = boto3.Session(
        aws_access_key_id=settings.ANSIBLE_AI_SEARCH["KEY"],
        aws_secret_access_key=settings.ANSIBLE_AI_SEARCH["SECRET"],
    ).get_credentials()
    auth = AWSV4SignerAuth(credentials, settings.ANSIBLE_AI_SEARCH["REGION"], "es")
elif settings.ANSIBLE_AI_SEARCH["KEY"]:
    auth = (settings.ANSIBLE_AI_SEARCH["KEY"], settings.ANSIBLE_AI_SEARCH["SECRET"])
else:
    auth = None


def initialize_OpenSearch():
    # Initialize AI Search only when settings.ANSIBLE_AI_SEARCH['HOST'] has a non-empty hostname.
    if settings.ANSIBLE_AI_SEARCH["HOST"]:
        client = OpenSearch(
            hosts=[
                {
                    "host": settings.ANSIBLE_AI_SEARCH["HOST"],
                    "port": settings.ANSIBLE_AI_SEARCH["PORT"],
                }
            ],
            http_auth=auth,
            use_ssl=settings.ANSIBLE_AI_SEARCH["USE_SSL"],
            verify_certs=settings.ANSIBLE_AI_SEARCH["VERIFY_CERTS"],
            connection_class=RequestsHttpConnection,
            pool_maxsize=20,
        )

        model = SentenceTransformer(
            f"sentence-transformers/{settings.ANSIBLE_AI_SEARCH['MODEL']}", device="cpu"
        )
    else:
        client = None
        model = None

    return client, model


client, model = initialize_OpenSearch()


def generate_query(encoded):
    return {
        "size": 3,
        "query": {
            "knn": {"output_body_vector": {"vector": encoded.tolist(), "k": 1}},
        },
        "fields": ["repo_name", "repo_url", "path", "license", "data_source", "type"],
    }


def search(suggestion):
    if client is None:
        raise Exception("AI Search is not initialized.")

    start_time = time.time()
    encoded = model.encode(sentences=suggestion, batch_size=16)
    encode_duration = round((time.time() - start_time) * 1000, 2)

    query = generate_query(encoded)

    start_time = time.time()
    results = client.search(index=settings.ANSIBLE_AI_SEARCH["INDEX"], body=query, _source=False)
    search_duration = round((time.time() - start_time) * 1000, 2)
    return {
        "attributions": [
            {
                "repo_name": result["fields"]["repo_name"][0],
                "repo_url": result["fields"]["repo_url"][0],
                "path": result["fields"]["path"][0],
                "license": result["fields"]["license"][0],
                "data_source": result["fields"]["data_source"][0],
                "ansible_type": result["fields"]["type"][0],
                "score": result["_score"],
            }
            for result in results["hits"]["hits"]
        ],
        "meta": {
            "encode_duration": encode_duration,
            "search_duration": search_duration,
        },
    }
