import json
from pathlib import Path


class VersionInfo:
    _image_tags = 'image-tags-not-defined'
    _git_commit = 'git-commit-not-defined'

    def __init__(self):
        try:
            version_info_file = Path(__file__).parent.parent / 'version_info.json'
            with open(version_info_file) as info:
                info_json = json.load(info)
                self._image_tags = info_json.imageTags
                self._git_commit = info_json.gitCommit
        except Exception:
            pass

    @property
    def image_tags(self):
        return self._image_tags

    @property
    def git_commit(self):
        return self._git_commit
