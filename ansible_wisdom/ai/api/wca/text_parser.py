import codecs

from django.conf import settings
from rest_framework.exceptions import ParseError
from rest_framework.parsers import BaseParser


class TextParser(BaseParser):
    """
    Parses Text-serialized data.
    """

    media_type = 'text/plain'

    def parse(self, stream, media_type=None, parser_context=None):
        """
        Parses the incoming bytestream as Text and returns the resulting data.
        """
        parser_context = parser_context or {}
        encoding = parser_context.get('encoding', settings.DEFAULT_CHARSET)

        try:
            decoded_stream = codecs.getreader(encoding)(stream)
            decoded = decoded_stream.decode(stream.body)
            return str(decoded[0])
        except UnicodeDecodeError as exc:
            raise ParseError(detail=exc)
