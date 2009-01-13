from errno import EAGAIN, EINTR
from subprocess import Popen, PIPE
import color
import cStringIO
import fcntl
import os
import select
import signal
import sys
import threading
import time
import traceback
import Queue

BUFFER_SIZE = 1 << 16

class ParallelPopen(object):
    def __init__(self, limit):
        self.limit = limit
        self.iomap = IOMap()

        self.tasks = []
        self.running = []
        self.done = []

    def add_task(self, task):
        if len(self.running) < self.limit:
            self.running.append(task)
            task.start()
        else:
            self.tasks.append(task)

    def wait(self):
        try:
            start_tasks()
            while True:
                self.iomap.poll()
                self.check_tasks()
        except KeyboardInterrupt:
            self.stop_all()

    def stop_all(self):
        for task in self.running:
            task.stop()

    def check_tasks(self):
        for task in self.running:
            pass

        while 0 < len(self.tasks) and len(self.running) < self.limit:
            task = self.tasks.pop(0)
            self.running.append(task)
            task.start()


class Task(object):
    def __init__(self, host, port, cmd, opts, stdin=None):
        self.host = host
        self.port = port
        self.cmd = cmd
        self.stdin = stdin
        self.outputbuffer = ""
        self.errorbuffer = ""
        self.exc_info = []
        self.exc_str = []

        self.proc = None
        self.iomap = None
        self.writer = None
        self.timestamp = None

        # Set options.
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

    def start(self, iomap, writer):
        self.writer = writer

        if self.stdin:
            stdin = PIPE
        else:
            stdin = None

        stdout = stderr = None
        if self.outdir:
            pathname = "%s/%s" % (self.outdir, self.host)
            self.outfile = open(pathname, "w")
            stdout = PIPE
        if self.errdir:
            pathname = "%s/%s" % (self.errdir, self.host)
            self.errfile = open(pathname, "w")
            stderr = PIPE
        if self.inline or self.print_out:
            stdout = stderr = PIPE

        # Create the subprocess.
        self.proc = Popen(self.cmd, stderr=stderr, stdin=stdin, stdout=stdout,
                close_fds=True, preexec_fn=os.setsid)
        self.timestamp = time.time()
        if stdin:
            self.fileno_stdin = self.proc.stdin.fileno()
            iomap.register(self.fileno_stdin, self.handle_stdin, write=True)
        if stdout:
            self.fileno_stdout = self.proc.stdout.fileno()
            iomap.register(self.fileno_stdout, self.handle_stdout, read=True)
        if stderr:
            self.fileno_stderr = self.proc.stderr.fileno()
            iomap.register(self.fileno_stderr, self.handle_stderr, read=True)

    def stop(self):
        os.kill(-self.proc.pid, signal.SIGKILL)
        # TODO: save a message that notes that this was interrupted!

    def timeleft(self):
        if self.timeout and self.timeout > 0:
            return self.timeout - (time.time() - self.timestamp)

    def handle_stdin(self, fd, event):
        try:
            bytes_written = os.write(fd, self.stdin)
        except:
            self.close_stdin()
            self.log_exception(e)
        self.stdin = self.stdin[bytes_written:]

    def close_stdin(self):
        if self.fileno_stdin:
            self.iomap.unregister(self.fileno_stdin)
            os.close(self.fileno_stdin)
            self.fileno_stdin = None

    def handle_stdout(self, fd, event):
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
                self.close_stdout()
        except (OSError, IOError), e:
            self.close_stdout()
            self.log_exception(e)

    def close_stdout(self):
        if self.fileno_stdout:
            self.iomap.unregister(self.fileno_stdout)
            os.close(self.fileno_stdout)
            self.fileno_stdout = None
        if self.outfile:
            self.writer.write(self.outfile, Writer.EOF)
            self.outfile = None

    def handle_stderr(self, fd, event):
        try:
            buf = os.read(fd, BUFFER_SIZE)
            if buf:
                if self.inline:
                    self.errorbuffer += buf
                if self.errfile:
                    self.writer.write(self.errfile, buf)
            else:
                self.close_stderr()
        except Exception, e:
            self.close_stderr()
            self.log_exception(e)

    def close_stderr(self):
        if self.fileno_stderr:
            self.iomap.unregister(self.fileno_stderr)
            os.close(self.fileno_stderr)
            self.fileno_stderr = None
        if self.errfile:
            self.writer.write(self.errfile, Writer.EOF)
            self.errfile = None

    def log_exception(self, e):
        self.exc_info.append(sys.exc_info())
        self.exc_str.append(str(e))

    def log_completion(self, n):
        tstamp = time.asctime().split()[3] # Current time
        if self.verbose:
            exceptions = []
            for exc_type, exc_value, exc_traceback in self.exc_info:
                exceptions.append("Exception: %s, %s, %s" % 
                    (exc_type, exc_value, traceback.format_tb(exc_traceback)))
            exc = '\n'.join(exceptions)
        else:
            exc = ', '.join(self.exc_str)
        if color.has_colors(sys.stdout):
            progress = color.c("[%s]" % color.B(n))
            success = color.g("[%s]" % color.B("SUCCESS"))
            failure = color.r("[%s]" % color.B("FAILURE"))
            stderr = color.r("Standard error:"))
            exc = color.r(color.B(exc))
        else:
            progress = "[%s]" % n
            success = "[SUCCESS]"
            failure = "[FAILURE]"
            stderr = "Standard error:"
        if exceptions
            print progress, tstamp, failure, self.host, self.port, exc
        else:
            print progress, tstamp, success, self.host, self.port
        if self.outputbuffer:
            print self.outputbuffer,
        if self.errorbuffer:
            print stderr, self.errorbuffer,
        sys.stdout.flush()


class Writer(threading.Thread):
    EOF = object()

    def __init__(self):
        threading.Thread.__init__(self)
        self.queue = Queue.Queue()

    def write(self, fd, data):
        """Called from another thread to enqueue a write."""
        self.queue.put((fd, data))

    def run(self):
        while True:
            file, data = self.queue.get()
            if file == self.EOF:
                file.close()
            else:
                print >>file, data,


class IOMap(object):
    def __init__(self):
        self.map = {}
        self.poller = select.poll()

    def register(self, fd, handler, read=False, write=False):
        """Registers an IO handler for a file descriptor.
        
        Either read or write (or both) must be specified.
        """
        self.map[fd] = handler

        eventmask = 0
        if read:
            eventmask |= select.POLLIN
        if write:
            eventmask |= select.POLLOUT
        if not eventmask:
            raise ValueError("Register must be called with read or write.")
        self.poller.register(fd, eventmask)

    def unregister(self, fd):
        """Unregisters the given file descriptor."""
        self.poller.unregister(fd)
        del self.map[fd]

    def poll(self, timeout=None):
        """Performs a poll and dispatches the resulting events."""
        for fd, event in self.poller.poll(timeout):
            handler = self.map[fd]
            handler(fd, event)

