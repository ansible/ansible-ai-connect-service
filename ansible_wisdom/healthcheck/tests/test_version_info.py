from unittest import TestCase, mock

from ..version_info import VersionInfo


class TestVersionInfo(TestCase):
    def test_version_info(self):
        version_info = VersionInfo()
        self.assertIsNotNone(version_info.image_tags)
        self.assertIsNotNone(version_info.git_commit)

    @mock.patch('json.load', side_effect=Exception)
    def test_version_info_error(self, _):
        version_info = VersionInfo()
        self.assertIsNotNone(version_info.image_tags)
        self.assertIsNotNone(version_info.git_commit)

    @mock.patch(
        'json.load', return_value={"imageTags": "my-image-tag", "gitCommit": "my-git-commit-hash"}
    )
    def test_version_info_load(self, _):
        version_info = VersionInfo()
        self.assertEqual(version_info.image_tags, "my-image-tag")
        self.assertEqual(version_info.git_commit, "my-git-commit-hash")
