from subprocess import Popen, PIPE
import color
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
    """Executes commands in parallel.

    Tasks are added with add_task() and executed in parallel with run().

    Arguments:
        limit: Maximum number of commands running at once.
        timeout: Maximum allowed execution time in seconds.
    """
    def __init__(self, limit, timeout):
        self.limit = limit
        self.timeout = timeout
        self.iomap = IOMap()

        self.tasks = []
        self.running = []
        self.done = []

    def run(self):
        """Processes tasks previously added with add_task."""
        for task in self.tasks:
            if task.outdir or task.errdir:
                writer = Writer()
                writer.start()
                break
        else:
            writer = None

        try:
            self.start_tasks(writer)
            wait = None
            while self.running or self.tasks:
                if wait == None or wait < 1:
                    wait = 1
                self.iomap.poll(wait)
                self.check_tasks()
                wait = self.check_timeout()
        except KeyboardInterrupt:
            self.interrupted()

        if writer:
            writer.queue.put((Writer.ABORT, None))
            writer.join()

    def add_task(self, task):
        """Adds a Task to be processed with run()."""
        self.tasks.append(task)

    def start_tasks(self, writer):
        """Starts as many tasks as allowed."""
        while 0 < len(self.tasks) and len(self.running) < self.limit:
            task = self.tasks.pop(0)
            self.running.append(task)
            task.start(self.iomap, writer)

    def check_tasks(self):
        """Checks to see if any tasks have terminated."""
        still_running = []
        for task in self.running:
            if task.running():
                still_running.append(task)
            else:
                self.finished(task)
        self.running = still_running

    def check_timeout(self):
        """Kills timed-out processes and returns the lowest time left."""
        if self.timeout <= 0:
            return None

        min_timeleft = None
        for task in self.running:
            timeleft = self.timeout - task.elapsed()
            if timeleft <= 0:
                task.timedout()
                continue
            if min_timeleft is None or timeleft < min_timeleft:
                min_timeleft = timeleft

        return max(0, min_timeleft)

    def interrupted(self):
        """Cleans up after a keyboard interrupt."""
        for task in self.running:
            task.interrupted()
            self.finished(task)

        for task in self.tasks:
            task.cancel()
            self.finished(task)

    def finished(self, task):
        """Marks a task as complete and reports its status to stdout."""
        self.done.append(task)
        n = len(self.done)
        task.report(n)


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

    def start(self, iomap, writer):
        """Starts the process and registers files with the IOMap."""
        self.writer = writer

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


class IOMap(object):
    """A manager for file descriptors and their associated handlers.

    The poll method dispatches events to the appropriate handlers.
    """
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


class Writer(threading.Thread):
    """Thread that writes to files by processing requests from a Queue.

    Until AIO becomes widely available, it is impossible to make a nonblocking
    write to an ordinary file.  The Writer thread processes all writing to
    ordinary files so that the main thread can work without blocking.
    """
    EOF = object()
    ABORT = object()

    def __init__(self):
        threading.Thread.__init__(self)
        # A daemon thread automatically dies if the program is terminated.
        self.setDaemon(True)
        self.queue = Queue.Queue()

    def run(self):
        while True:
            file, data = self.queue.get()
            if file == self.ABORT:
                return
            if data == self.EOF:
                file.close()
            else:
                print >>file, data,

    def write(self, fd, data):
        """Called from another thread to enqueue a write."""
        self.queue.put((fd, data))
