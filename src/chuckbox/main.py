import os
import sys
import argparse

import chuckbox.log as log
import chuckbox.project as project
import chuckbox.package as package

REQUIREMENTS_FILE = 'project/install_requires.txt'

argparser = argparse.ArgumentParser(
    prog='chuckbox',
    description='chuckbox: sane Python project tools.')

subparsers = argparser.add_subparsers(
    dest='tool_name',
    title='Chuckbox Tools',
    description='Chuckbox supports several modular commands for Python project management.',
    help='Tools available.')

pack_parser = subparsers.add_parser('pack',
    help='Package a project.')

pack_parser.add_argument('name',
    help='Name of the project being packaged up.')

pack_parser.add_argument(
    '-p', '--path',
    default=os.getcwd(),
    help='Path to the project. If left unset the cwd is utilized')

argparser.add_argument(
    '-v', '--version',
    dest='wants_version',
    action='store_true',
    default=False,
    help="""Prints the version.""")

argparser.add_argument(
    '-d', '--debug',
    dest='wants_debug',
    action='store_true',
    default=False,
    help="""Enables debug output and code paths.""")

argparser.add_argument(
    '-q', '--quiet',
    dest='wants_quiet',
    action='store_true',
    default=False,
    help="""
        Sets the logging output to quiet. This supercedes enabling the
        debug output switch.""")


def init():
    about_cb = project.about('chuckbox')


    if len(sys.argv) > 1:
        log.get_log_manager().configure({
            'level': 'DEBUG',
            'console_enabled': True})

        args = argparser.parse_args()

        if args.wants_version:
            print('chuckbox version: {}'.format(about_cb.version))
            sys.exit(0)

        if args.tool_name == 'pack':
            version_file = os.path.join(
                args.path,'src/{name}/VERSION'.format(name=args.name))

            if not os.path.exists(version_file):
                print('Unable to locate version file: {vfile}'.format(
                    vfile=version_file))
                sys.exit(1)

            version = None

            with open(version_file, 'r') as vinfo:
                line = vinfo.readline()
                while line is not None:
                    if len(line) > 0:
                        version = line.strip()
                        break

            if version is None:
                print('No version info found in file: {vfile}'.format(
                    vfile=version_file))
                sys.exit(1)

            package.create(args.path, REQUIREMENTS_FILE, dict(), args.name, version)
    else:
        argparser.print_help()
