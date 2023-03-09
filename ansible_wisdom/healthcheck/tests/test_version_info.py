from unittest import TestCase

from ..version_info import VersionInfo


class TestVersionInfo(TestCase):
    def test_version_info(self):
        version_info = VersionInfo()
        self.assertIsNotNone(version_info.image_tags)
        self.assertIsNotNone(version_info.git_commit)
