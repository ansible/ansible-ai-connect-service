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

import json
from pathlib import Path


class VersionInfo:
    _image_tags = 'image-tags-not-defined'
    _git_commit = 'git-commit-not-defined'

    def __init__(self):
        version_info_file = Path(__file__).parent.parent / 'version_info.json'
        print("version_info path:", version_info_file)
        with open(version_info_file) as info:
            info_json = json.load(info)
            print("version_info", version_info_file, info_json)
            self._image_tags = info_json["imageTags"]
            self._git_commit = info_json["gitCommit"]

    @property
    def image_tags(self):
        return self._image_tags

    @property
    def git_commit(self):
        return self._git_commit
