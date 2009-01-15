from errno import EINTR
from subprocess import Popen, PIPE
import askpass
import color
import os
import signal
import sys
import time
import traceback

BUFFER_SIZE = 1 << 16

class Task(object):
    """Starts a process and manages its input and output."""
    def __init__(self, host, port, cmd, opts, stdin=None):
        self.host = host
        self.port = port
        self.cmd = cmd

        self.proc = None
        self.writer = None
        self.timestamp = None
        self.failures = []
        self.killed = False
        self.inputbuffer = stdin
        self.outputbuffer = ''
        self.errorbuffer = ''

        self.stdin = None
        self.stdout = None
        self.stderr = None
        self.outfile = None
        self.errfile = None

        # Set options.
        self.verbose = opts.verbose
        self.outdir = opts.outdir
        self.errdir = opts.errdir
        try:
            self.print_out = bool(opts.print_out)
        except AttributeError:
            self.print_out = False
        try:
            self.inline = bool(opts.inline)
        except AttributeError:
            self.inline = False

    def start(self, iomap, writer, askpass_socket=None):
        """Starts the process and registers files with the IOMap."""
        self.writer = writer

        if self.outdir:
            pathname = "%s/%s" % (self.outdir, self.host)
            self.outfile = open(pathname, "w")
        if self.errdir:
            pathname = "%s/%s" % (self.errdir, self.host)
            self.errfile = open(pathname, "w")

        # Create the subprocess.
        if askpass_socket:
            environ = dict(os.environ)
            environ['SSH_ASKPASS'] = os.path.abspath(askpass.__file__)
            environ['PSSH_ASKPASS_SOCKET'] = askpass_socket
        else:
            environ = None
        self.proc = Popen([self.cmd], stdin=PIPE, stdout=PIPE, stderr=PIPE,
                close_fds=True, preexec_fn=os.setsid, env=environ, shell=True)
        self.timestamp = time.time()
        if self.inputbuffer:
            self.stdin = self.proc.stdin
            iomap.register(self.stdin.fileno(), self.handle_stdin, write=True)
        else:
            self.proc.stdin.close()
        self.stdout = self.proc.stdout
        iomap.register(self.stdout.fileno(), self.handle_stdout, read=True)
        self.stderr = self.proc.stderr
        iomap.register(self.stderr.fileno(), self.handle_stderr, read=True)

    def _kill(self):
        """Signals the process to terminate."""
        if self.proc:
            os.kill(-self.proc.pid, signal.SIGKILL)
            self.killed = True

    def timedout(self):
        """Kills the process and registers a timeout error."""
        if not self.killed:
            self._kill()
            self.failures.append('Timed out')

    def interrupted(self):
        """Kills the process and registers an keyboard interrupt error."""
        if not self.killed:
            self._kill()
            self.failures.append('Interrupted')

    def cancel(self):
        """Stops a task that has not started."""
        self.failures.append('Cancelled')

    def elapsed(self):
        """Finds the time in seconds since the process was started."""
        return time.time() - self.timestamp

    def running(self):
        """Finds if the process has terminated and saves the return code."""
        if self.stdin or self.stdout or self.stderr:
            return True
        if self.proc:
            self.returncode = self.proc.poll()
            if self.returncode is None:
                if self.killed:
                    return False
                else:
                    return True
            else:
                if self.returncode < 0:
                    message = 'Killed by signal %s' % (-self.returncode)
                    self.failures.append(message)
                elif self.returncode > 0:
                    message = 'Exited with error code %s' % self.returncode
                    self.failures.append(message)
                self.proc = None
                return False

    def handle_stdin(self, fd, event, iomap):
        try:
            if self.inputbuffer:
                bytes_written = os.write(fd, self.inputbuffer)
                self.inputbuffer = self.inputbuffer[bytes_written:]
            else:
                self.close_stdin(iomap)
        except (OSError, IOError), e:
            if e.errno != EINTR:
                self.close_stdin(iomap)
                self.log_exception(e)

    def close_stdin(self, iomap):
        if self.stdin:
            iomap.unregister(self.stdin.fileno())
            self.stdin.close()
            self.stdin = None

    def handle_stdout(self, fd, event, iomap):
        try:
            buf = os.read(fd, BUFFER_SIZE)
            if buf:
                if self.inline:
                    self.outputbuffer += buf
                if self.outfile:
                    self.writer.write(self.outfile, buf)
                if self.print_out:
                    print '%s: %s' % (self.host, buf),
            else:
                self.close_stdout(iomap)
        except (OSError, IOError), e:
            if e.errno != EINTR:
                self.close_stdout(iomap)
                self.log_exception(e)

    def close_stdout(self, iomap):
        if self.stdout:
            iomap.unregister(self.stdout.fileno())
            self.stdout.close()
            self.stdout = None
        if self.outfile:
            self.writer.write(self.outfile, Writer.EOF)
            self.outfile = None

    def handle_stderr(self, fd, event, iomap):
        try:
            buf = os.read(fd, BUFFER_SIZE)
            if buf:
                if self.inline:
                    self.errorbuffer += buf
                if self.errfile:
                    self.writer.write(self.errfile, buf)
            else:
                self.close_stderr(iomap)
        except (OSError, IOError), e:
            if e.errno != EINTR:
                self.close_stderr(iomap)
                self.log_exception(e)

    def close_stderr(self, iomap):
        if self.stderr:
            iomap.unregister(self.stderr.fileno())
            self.stderr.close()
            self.stderr = None
        if self.errfile:
            self.writer.write(self.errfile, Writer.EOF)
            self.errfile = None

    def log_exception(self, e):
        """Saves a record of the most recent exception for error reporting."""
        if self.verbose:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            exc = ("Exception: %s, %s, %s" % 
                    (exc_type, exc_value, traceback.format_tb(exc_traceback)))
        else:
            exc = str(e)
        self.failures.append(exc)

    def report(self, n):
        """Pretty prints a status report after the Task completes."""
        error = ', '.join(self.failures)
        tstamp = time.asctime().split()[3] # Current time
        if color.has_colors(sys.stdout):
            progress = color.c("[%s]" % color.B(n))
            success = color.g("[%s]" % color.B("SUCCESS"))
            failure = color.r("[%s]" % color.B("FAILURE"))
            stderr = color.r("Standard error:")
            error = color.r(color.B(error))
        else:
            progress = "[%s]" % n
            success = "[SUCCESS]"
            failure = "[FAILURE]"
            stderr = "Standard error:"
        if self.failures:
            print progress, tstamp, failure, self.host, self.port, error
        else:
            print progress, tstamp, success, self.host, self.port
        if self.outputbuffer:
            print self.outputbuffer,
        if self.errorbuffer:
            print stderr, self.errorbuffer,
        sys.stdout.flush()

