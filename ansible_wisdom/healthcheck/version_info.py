from configparser import ConfigParser
from pathlib import Path


class VersionInfo:
    _image_tags = 'image-tags-not-defined'
    _git_commit = 'git-commit-not-defined'

    def __init__(self):
        try:
            ini_file = Path(__file__).parent.parent / 'version_info.ini'
            with open(ini_file) as INI:
                configparser = ConfigParser()
                configparser.read_file(INI)
                self._image_tags = configparser['ansible-wisdom-service']['IMAGE_TAGS']
                self._git_commit = configparser['ansible-wisdom-service']['GIT_COMMIT']
        except Exception:
            pass
        finally:
            return

    @property
    def image_tags(self):
        return self._image_tags

    @property
    def git_commit(self):
        return self._git_commit
