import subprocess


class CommandResult(object):

    def __init__(self, returncode, output):
        self.returncode = returncode
        self._output = output

    def __str__(self):
        return 'CommandResult with returncode: {returncode}'.format(
            returncode=self.returncode)

    @property
    def output(self):
        return self._output.replace('\n', '')

    @property
    def content(self):
        return self._output


class CommandError(Exception):

    def __init__(self, result, *args, **kwargs):
        super(CommandError, self).__init__(args, kwargs)
        self.result = result


def run_command(cmd, cwd=None, env=None):
    output = bytearray()
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        shell=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        close_fds=True)

    while proc.poll() is None:
        line = proc.stdout.readline()

        if line is None:
            break

        output.extend(line)

    result = CommandResult(proc.returncode, output)

    if result.returncode and result.returncode != 0:
        raise CommandError(result)

    return result
