import os
import stat
import sys
import shutil
import tempfile
import subprocess
import urllib2
import tarfile
import logging
import zipfile

import chuckbox.log as log
import chuckbox.cmd as cmd

from pip.download import unpack_http_url
from pip.index import PackageFinder
from pip.req import InstallRequirement, RequirementSet
from pip.locations import build_prefix, src_prefix


_LOG = log.get_logger(__name__)


class BuildLocations(object):

    def __init__(self, ctx_root):
        self.root = _mkdir(os.path.join(ctx_root, 'build'))
        self.dist = _mkdir(os.path.join(ctx_root, 'dist'))
        self.dist_lib = _mkdir(os.path.join(self.dist, 'lib'))
        self.dist_python = _mkdir(os.path.join(self.dist_lib, 'python'))
        self.files = _mkdir(os.path.join(ctx_root, 'files'))


class DeploymentLocations(object):

    def __init__(self, ctx_root, project_name):
        self.root = _mkdir(os.path.join(ctx_root, 'layout'))

        self.usr = _mkdir(os.path.join(self.root, 'usr'))
        self.usr_share = _mkdir(os.path.join(self.usr, 'share'))
        self.project_share = _mkdir(os.path.join(self.usr_share, project_name))

        self.etc = _mkdir(os.path.join(self.root, 'etc'))
        self.init_d = _mkdir(os.path.join(self.etc, 'init.d'))


class BuildContext(object):

    def __init__(self, ctx_root, pkg_index, project_name):
        self.root = ctx_root
        self.pkg_index = pkg_index
        self.deploy = DeploymentLocations(ctx_root, project_name)
        self.build = BuildLocations(ctx_root)


def _read(relative):
    contents = open(relative, 'r').read()
    return [l for l in contents.split('\n') if len(l) > 0]


def _mkdir(location):
    if not os.path.exists(location):
        os.mkdir(location)
    return location


def _download(url, dl_location):
    u = urllib2.urlopen(url)
    localFile = open(dl_location, 'w')
    localFile.write(u.read())
    localFile.close()


def _runpy(bctx, cmd_str, cwd=None):
    env = os.environ.copy()
    env['PYTHONPATH'] = '{}:{}'.format('./src/', bctx.build.dist_python)

    try:
        result = cmd.run_command(cmd_str, cwd, env)
    except cmd.CommandError as err:
        _LOG.exception(err)
        result = err.result

    if result is not None:
        _LOG.info(result.content)

        if result.returncode != 0:
            _LOG.error('Failure in command: {}'.format(cmd_str))
            sys.exit(1)
    else:
        _LOG.error('None result. Assuming timeout and exiting for command: {}'.format(cmd_str))
        sys.exit(1)


def _unpack(name, bctx, stage_hooks, filename, dl_target):
    if dl_target.endswith('.tar.gz') or dl_target.endswith('.tgz'):
        archive = tarfile.open(dl_target, mode='r|gz')
        build_location = os.path.join(
            bctx.build.root, filename.rstrip('.tar.gz'))
    elif dl_target.endswith('.zip'):
        archive = zipfile.ZipFile(dl_target, mode='r')
        build_location = os.path.join(bctx.build.root, filename.rstrip('.zip'))
    else:
        _LOG.info('Unknown archive format: {}'.format(dl_target))
        raise Exception()

    archive.extractall(bctx.build.root)
    return build_location


def _install(name, bctx, stage_hooks=None):
    req = InstallRequirement.from_line(name, None)
    found_req = bctx.pkg_index.find_requirement(req, False)
    dl_target = os.path.join(bctx.build.files, found_req.filename)

    # stages - TODO: Clean this up with ContextManager x.x
    _hook(name, 'download.before',
              stage_hooks, bctx=bctx, fetch_url=found_req.url)
    _download(found_req.url, dl_target)
    _hook(name, 'download.after',
              stage_hooks, bctx=bctx, archive=dl_target)

    _hook(name, 'unpack.before',
              stage_hooks, bctx=bctx, archive=dl_target)
    build_location = _unpack(
        name, bctx, stage_hooks, found_req.filename, dl_target)
    _hook(name, 'unpack.after',
              stage_hooks, bctx=bctx, build_location=build_location)

    _hook(name, 'build.before',
              stage_hooks, bctx=bctx, build_location=build_location)
    _runpy(bctx,
        'python setup.py build'.format(build_location),
        build_location)
    _hook(name, 'build.after',
              stage_hooks, bctx=bctx, build_location=build_location)

    _hook(name, 'install.before',
              stage_hooks, bctx=bctx, build_location=build_location)
    _runpy(bctx,
        'python setup.py install --home={}'.format(bctx.build.dist),
        build_location)
    _hook(name, 'install.after',
              stage_hooks, bctx=bctx, build_location=build_location)


def _hook(name, stage, stage_hooks, **kwargs):
    if stage_hooks:
        if name in stage_hooks:
            hooks = stage_hooks[name]
            if stage in hooks:
                hook = hooks[stage]
                _LOG.info('Calling hook {} for stage {}'.format(hook, stage))
                hook(kwargs)


def _read_requires(filename, bctx, pkg_index, hooks):
    lines = open(filename, 'r').read()

    if lines is not None and len(lines) > 0:
        for line in lines.split('\n'):
            if line and len(line) > 0:
                _install(line, bctx, hooks)


def _copytree(src, dst, symlinks=False):
    names = os.listdir(src)
    if not os.path.exists(dst):
        os.makedirs(dst)

    for name in names:
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)

        if symlinks and os.path.islink(srcname):
            linkto = os.readlink(srcname)
            os.symlink(linkto, dstname)
        elif os.path.isdir(srcname):
            _copytree(srcname, dstname, symlinks)
        else:
            shutil.copy2(srcname, dstname)


def create(path, requirements_file, hooks, project_name, version):
    # Track where we are and then head where we need to go
    cwd = os.getcwd()
    os.chdir(path)

    # Pip package finder is used to locate dependencies for downloading
    pkg_index = PackageFinder(
        find_links=[],
        index_urls=["http://pypi.python.org/simple/"])

    # Build context holds all of the directories and state information
    bctx = BuildContext(tempfile.mkdtemp(), pkg_index, project_name)

    # Build the project requirements and install them
    _read_requires(requirements_file, bctx, pkg_index, hooks)

    # Build root after requirements are finished
    _runpy(bctx, 'python setup.py build')
    _runpy(bctx, 'python setup.py install --home={}'.format(
        bctx.build.dist))

    # Copy all of the important files into their intended destinations
    local_layout = os.path.join('.', 'pkg/layout')
    if os.path.exists(local_layout):
        _copytree(local_layout, bctx.deploy.root)

    # Copy the built virtualenv
    _copytree(bctx.build.dist, bctx.deploy.project_share)

    # Let's build a tarfile
    tar_filename = '{}_{}.tar.gz'.format(project_name, version)
    tar_fpath = os.path.join(bctx.root, tar_filename)

    # Open the
    tarchive = tarfile.open(tar_fpath, 'w|gz')
    tarchive.add(bctx.deploy.root, arcname='')
    tarchive.close()

    # Pop back to our original working directory
    os.chdir(cwd)


    # Copy the finished tafile
    shutil.copyfile(tar_fpath, os.path.join('.', tar_filename))

    # Clean the build dir
    _LOG.info('Cleaning {}'.format(bctx.root))
    shutil.rmtree(bctx.root)
