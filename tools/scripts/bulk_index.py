import argparse
import os

import pandas as pd
import tqdm
from elasticsearch import Elasticsearch
from elasticsearch.helpers import streaming_bulk
from sentence_transformers import SentenceTransformer


def generate_encodings(df):
    model = SentenceTransformer(f'sentence-transformers/{args.model}')
    encoded_output = model.encode(df['output_script'])
    df['output_script_vector'] = model.encode(df['output_script']).tolist()

    for row in df.iterrows():
        yield row[1].to_json()


def main():
    print("loading dataset")
    df = pd.read_json(path_or_buf=args.dataset, lines=True)
    client = Elasticsearch(os.getenv('ELASTICSEARCH_URI', 'http://localhost:9200'))

    number_of_docs = len(df)
    progress = tqdm.tqdm(unit="docs", total=number_of_docs)
    successes = 0
    for ok, action in streaming_bulk(
        client=client, index=args.index, actions=generate_encodings(df)
    ):
        progress.update(1)
        successes += ok


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generating bulk load file')
    parser.add_argument('--dataset', required=True, help='path to dataset file "awgold*"')
    parser.add_argument('--model', default='msmarco-distilbert-base-tas-b', help='NLP model to use')
    parser.add_argument('--index', required=True, help='Elasticsearch index')
    args = parser.parse_args()
    main()
