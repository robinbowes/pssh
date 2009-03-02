from askpass import PasswordServer
from errno import EINTR
import os
import select
import threading
import Queue

class Manager(object):
    """Executes tasks concurrently.

    Tasks are added with add_task() and executed in parallel with run().

    Arguments:
        limit: Maximum number of commands running at once.
        timeout: Maximum allowed execution time in seconds.
    """
    def __init__(self, opts):
        self.limit = opts.par
        self.timeout = opts.timeout
        self.askpass = opts.askpass
        self.outdir = opts.outdir
        self.errdir = opts.errdir
        self.iomap = IOMap()

        self.tasks = []
        self.running = []
        self.done = []

        self.askpass_socket = None

    def run(self):
        """Processes tasks previously added with add_task."""
        try:
            if self.outdir or self.errdir:
                writer = Writer(self.outdir, self.errdir)
                writer.start()
            else:
                writer = None

            if self.askpass:
                pass_server = PasswordServer()
                pass_server.start(self.iomap, self.limit)
                self.askpass_socket = pass_server.address

            try:
                self.start_tasks(writer)
                wait = None
                while self.running or self.tasks:
                    if wait == None or wait < 1:
                        wait = 1
                    self.iomap.poll(wait)
                    self.check_tasks()
                    self.start_tasks(writer)
                    wait = self.check_timeout()
            except KeyboardInterrupt:
                # This exception handler tries to clean things up and prints
                # out a nice status message for each interrupted host.
                self.interrupted()

        except KeyboardInterrupt:
            # This exception handler doesn't print out any fancy status
            # information--it just stops.
            pass

        if writer:
            writer.signal_quit()
            writer.join()

    def add_task(self, task):
        """Adds a Task to be processed with run()."""
        self.tasks.append(task)

    def start_tasks(self, writer):
        """Starts as many tasks as allowed."""
        while 0 < len(self.tasks) and len(self.running) < self.limit:
            task = self.tasks.pop(0)
            self.running.append(task)
            task.start(self.iomap, writer, self.askpass_socket)

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
        try:
            events = self.poller.poll(timeout)
        except select.error, e:
            errno, message = e.args
            if errno == EINTR:
                return
            else:
                raise
        for fd, event in events:
            handler = self.map[fd]
            handler(fd, event, self)


class Writer(threading.Thread):
    """Thread that writes to files by processing requests from a Queue.

    Until AIO becomes widely available, it is impossible to make a nonblocking
    write to an ordinary file.  The Writer thread processes all writing to
    ordinary files so that the main thread can work without blocking.
    """
    OPEN = object()
    EOF = object()
    ABORT = object()

    def __init__(self, outdir, errdir):
        threading.Thread.__init__(self)
        # A daemon thread automatically dies if the program is terminated.
        self.setDaemon(True)
        self.queue = Queue.Queue()
        self.outdir = outdir
        self.errdir = errdir

        self.host_counts = {}
        self.files = {}

    def run(self):
        while True:
            filename, data = self.queue.get()
            if filename == self.ABORT:
                return

            if data == self.OPEN:
                self.files[filename] = open(filename, 'w', buffering=1)
            else:
                dest = self.files[filename]
                if data == self.EOF:
                    dest.close()
                else:
                    print >>dest, data,

    def open_files(self, host):
        """Called from another thread to create files for stdout and stderr.
        
        Returns a pair of filenames (outfile, errfile).  These filenames are
        used as handles for future operations.  Either or both may be None if
        outdir or errdir or not set.
        """
        outfile = errfile = None
        if self.outdir or self.errdir:
            count = self.host_counts.get(host, 0)
            self.host_counts[host] = count + 1
            if count:
                filename = "%s.%s" % (host, count)
            else:
                filename = host
            if self.outdir:
                outfile = os.path.join(self.outdir, filename)
                self.queue.put((outfile, self.OPEN))
            if self.errdir:
                errfile = os.path.join(self.errdir, filename)
                self.queue.put((errfile, self.OPEN))
        return outfile, errfile

    def write(self, filename, data):
        """Called from another thread to enqueue a write."""
        self.queue.put((filename, data))

    def close(self, filename):
        """Called from another thread to close the given file."""
        self.queue.put((filename, self.EOF))

    def signal_quit(self):
        """Called from another thread to request the Writer to quit."""
        self.queue.put((self.ABORT, None))

