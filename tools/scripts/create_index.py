import argparse
import json
import os

from elasticsearch import Elasticsearch


def main():
    print(f'Creating index {args.index}')
    client = Elasticsearch(os.getenv('ELASTICSEARCH_URI', 'http://localhost:9200'))
    with open(args.index_file) as index:
        body = json.load(index)
    client.indices.create(index=args.index, settings=body['settings'], mappings=body['mappings'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create Elasticsearch index')
    parser.add_argument(
        '--index-file', required=True, help='Name of the file containing the JSON index definition'
    )
    parser.add_argument('--index', required=True, help='Elasticsearch index')
    args = parser.parse_args()
    main()
