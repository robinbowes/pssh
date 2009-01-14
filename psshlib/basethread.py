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
    def __init__(self, limit, timeout):
        self.limit = limit
        self.timeout = timeout
        self.iomap = IOMap()

        self.tasks = []
        self.running = []
        self.done = []

    def add_task(self, task):
        self.tasks.append(task)

    def run(self):
        writer = Writer()
        writer.start()

        try:
            self.start_tasks(writer)
            timeout = None
            while self.running or self.tasks:
                self.iomap.poll(timeout)
                self.check_tasks()
                timeout = self.check_timeout()
        except KeyboardInterrupt:
            print 'got keyboard interrupt'
            self.stop_all()

        # TODO: finish task cleanup here

        writer.queue.put((Writer.ABORT, None))
        writer.join()

    def start_tasks(self, writer):
        while 0 < len(self.tasks) and len(self.running) < self.limit:
            task = self.tasks.pop(0)
            self.running.append(task)
            task.start(self.iomap, writer)

    def stop_all(self):
        for task in self.running:
            task.stop()

    def check_tasks(self):
        still_running = []
        for task in self.running:
            if task.running():
                still_running.append(task)
            else:
                self.done.append(task)
                n = len(self.done)
                task.report(n)
        self.running = still_running

    def check_timeout(self):
        """Kills timed-out processes and returns the lowest time left."""

        if self.timeout <= 0:
            return None

        min_timeleft = None
        for task in self.running:
            timeleft = self.timeout - task.elapsed()
            if timeleft <= 0:
                task.stop()
                continue
            if min_timeleft is None or timeleft < min_timeleft:
                min_timeleft = timeleft

        return max(0, min_timeleft)


class Task(object):
    def __init__(self, host, port, cmd, opts, stdin=None):
        self.host = host
        self.port = port
        self.cmd = cmd

        self.proc = None
        self.writer = None
        self.timestamp = None

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

        self.stdin = None
        self.stdout = None
        self.stderr = None
        self.inputbuffer = stdin
        self.outputbuffer = ''
        self.outfile = None
        self.errorbuffer = ''
        self.errfile = None
        self.exc_info = []
        self.exc_str = []

    def start(self, iomap, writer):
        self.writer = writer

        if self.stdin:
            stdin = PIPE
        else:
            stdin = None

        if self.outdir:
            pathname = "%s/%s" % (self.outdir, self.host)
            self.outfile = open(pathname, "w")
        if self.errdir:
            pathname = "%s/%s" % (self.errdir, self.host)
            self.errfile = open(pathname, "w")

        # Create the subprocess.
        self.proc = Popen([self.cmd], stdin=PIPE, stdout=PIPE, stderr=PIPE,
                close_fds=True, preexec_fn=os.setsid, shell=True)
        self.timestamp = time.time()
        if stdin:
            self.stdin = self.proc.stdin
            iomap.register(self.stdin.fileno(), self.handle_stdin, write=True)
        else:
            self.proc.stdin.close()
        self.stdout = self.proc.stdout
        iomap.register(self.stdout.fileno(), self.handle_stdout, read=True)
        self.stderr = self.proc.stderr
        iomap.register(self.stderr.fileno(), self.handle_stderr, read=True)

    def stop(self):
        if self.proc:
            os.kill(-self.proc.pid, signal.SIGKILL)
            # TODO: save a message that notes that this was interrupted!

    def elapsed(self):
        return time.time() - self.timestamp

    def running(self):
        if self.stdin or self.stdout or self.stderr:
            return True
        if self.proc:
            self.returncode = self.proc.poll()
            if self.returncode is None:
                return True
            else:
                self.proc = None
                return False

    def handle_stdin(self, fd, event, iomap):
        try:
            bytes_written = os.write(fd, self.stdin)
        except (OSError, IOError), e:
            self.close_stdin(iomap)
            self.log_exception(e)
        self.stdin = self.stdin[bytes_written:]

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
        self.exc_info.append(sys.exc_info())
        self.exc_str.append(str(e))

    def report(self, n):
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
            stderr = color.r("Standard error:")
            exc = color.r(color.B(exc))
        else:
            progress = "[%s]" % n
            success = "[SUCCESS]"
            failure = "[FAILURE]"
            stderr = "Standard error:"
        if self.exc_info:
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
    ABORT = object()

    def __init__(self):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.queue = Queue.Queue()

    def write(self, fd, data):
        """Called from another thread to enqueue a write."""
        self.queue.put((fd, data))

    def run(self):
        while True:
            file, data = self.queue.get()
            if file == self.ABORT:
                return
            if data == self.EOF:
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
            handler(fd, event, self)

