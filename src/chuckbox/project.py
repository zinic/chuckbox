import os
import importlib

import chuckbox.log as log

_LOG = log.get_logger(__name__)


class MissingResourceError(Exception):
    pass


class PackageManifest(object):

    def __init__(self, name, module):
        self.name = name
        self._module = module

    def find(self, relative):
        return FindResource(relative).in_paths(self._module.__path__)

    @property
    def version(self):
        resource = FindResource('VERSION').in_paths(self._module.__path__)

        with open(resource, 'r') as fin:
            version = fin.readline()
            if len(version) > 0:
                return version

        raise MissingResourceError((
            'No suitable version info found. Expected a "VERSION" file in '
            'the root path of module {name}.').format(name=self.name))


class FindResource(object):

    def __init__(self, resource):
        self._resource = resource

    def in_paths(self, paths):
        for path in paths:
            full_path = os.path.join(path, self._resource)

            if os.path.exists(full_path):
                return full_path
        raise MissingResourceError(path)


def about(pkg):
    module = importlib.import_module(pkg)
    return PackageManifest(pkg, module)
