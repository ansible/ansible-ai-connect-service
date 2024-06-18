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

from unittest import TestCase, mock

from ..version_info import VersionInfo


class TestVersionInfo(TestCase):
    def test_version_info(self):
        version_info = VersionInfo()
        self.assertIsNotNone(version_info.image_tags)
        self.assertIsNotNone(version_info.git_commit)

    @mock.patch("json.load", side_effect=Exception)
    def test_version_info_error(self, _):
        version_info = VersionInfo()
        self.assertIsNotNone(version_info.image_tags)
        self.assertIsNotNone(version_info.git_commit)

    @mock.patch(
        "json.load", return_value={"imageTags": "my-image-tag", "gitCommit": "my-git-commit-hash"}
    )
    def test_version_info_load(self, _):
        version_info = VersionInfo()
        self.assertEqual(version_info.image_tags, "my-image-tag")
        self.assertEqual(version_info.git_commit, "my-git-commit-hash")
