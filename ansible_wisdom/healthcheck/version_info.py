from configparser import ConfigParser


class VersionInfo:
    _image_tags = 'image-tags-not-defined'
    _git_commit = 'git-commit-not-defined'

    def __init__(self):
        with open('version_info.ini') as INI:
            try:
                configparser = ConfigParser()
                configparser.read('version_info.ini')
                self._image_tags = configparser['ansible-wisdom-service']['IMAGE_TAGS']
                self._git_commit = configparser['ansible-wisdom-service']['GIT_COMMIT']
            finally:
                return

    @property
    def image_tags(self):
        return self._image_tags

    @property
    def git_commit(self):
        return self._git_commit
