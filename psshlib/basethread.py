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

class BaseThread(threading.Thread):
    def __init__(self, host, port, cmd, flags, sem, stdin=None):
        threading.Thread.__init__(self)
        self.host = host
        self.port = port
        self.cmd = cmd
        self.flags = flags
        self.sem = sem
        self.stdin = stdin
        self.outputbuffer = ""

    def select_wrap(self, rlist, wlist, elist, timeout):
        """
        Perform a select on rlist, wlist, elist with the specified
        timeout while retrying if the the select call is interrupted
        because of a signal.  If timeout is None, this method never
        times out.
        """
        t1 = time.time()
        while True:
            try:
                t2 = time.time()
                if timeout is not None:
                    t = max(0, timeout - (t2 - t1))
                    r, w, e = select.select(rlist, wlist, elist, t)
                else: # No timeout
                    r, w, e = select.select(rlist, wlist, elist)
                return r, w, e
            except select.error, e:
                if e.args[0] == EINTR:
                    continue
                raise

    def async_read_wrap(self, fd, nbytes):
       """Read up to nbytes from fd (or less if would block"""
       buf = cStringIO.StringIO()
       while len(buf.getvalue()) != nbytes:
          try:
              chunk = os.read(fd, nbytes - len(buf.getvalue()))
              if len(chunk) == 0:
                  return buf.getvalue() # EOF, so return
              buf.write(chunk)
          except OSError, e:
              if e.errno == EINTR:
                  continue
              elif e.errno == EAGAIN:
                  return buf.getvalue() 
              raise
       return buf.getvalue()

    def write_wrap(self, fd, data):
        """Write data to fd (assumes a blocking fd)"""
        bytesWritten = 0
        while bytesWritten != len(data):
            try:
                n = os.write(fd, data[bytesWritten:])
                bytesWritten += n
            except OSError, e:
                if e.errno == EINTR:
                    continue
                raise

    def run(self):
        done = None
        stdout = cStringIO.StringIO()
        stderr = cStringIO.StringIO()
        child = Popen([self.cmd], stderr=PIPE, stdin=PIPE, stdout=PIPE,
                      close_fds=True, preexec_fn=os.setsid, shell=True)
        try:
            cstdout = child.stdout
            cstderr = child.stderr
            cstdin = child.stdin
            if self.stdin:
                self.write_wrap(cstdin.fileno(), self.stdin)
                cstdin.close()
                del self.stdin # Throw away stdin input, since we don't need it
            iomap = { cstdout : stdout, cstderr : stderr }
            fcntl.fcntl(cstdout.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)
            fcntl.fcntl(cstderr.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)
            start = time.time()
            status = -1 # Set status to -1 for other errors (timeout, etc.)
            while 1:
                if self.flags["timeout"] is not None:
                    timeout = self.flags["timeout"] - (time.time() - start)
                    if timeout <= 0:
                        raise Exception("Timeout")
                    r, w, e = self.select_wrap([ cstdout, cstderr ], 
                                               [], [], timeout)
                else: # No timeout
                    r, w, e = self.select_wrap([ cstdout, cstderr ], 
                                               [], [], None)
                try:
                    for f in r:
                        chunk = self.async_read_wrap(f.fileno(), 1 << 16)
                        if len(chunk) == 0:
                            done = 1
                        iomap[f].write(chunk)                    
                        if self.flags.has_key("print") and self.flags["print"]:
                            to_write = "%s: %s" % (self.host, chunk)
                            self.write_wrap(sys.stdout.fileno(), to_write)
                        if self.flags.has_key("inline") and \
                               self.flags["inline"] and len(chunk) > 0:
                            self.outputbuffer += chunk # Small output only
                    if done:
                        break
                except:
                    os.kill(child.pid, signal.SIGKILL)
                    raise
            status = child.wait() # Shouldn't block (just to get status)
            if status:
                raise Exception("Received error code of %d" % status)
            log_completion(self.host, self.port, self.outputbuffer)
            self.write_output(stdout, stderr)
        except Exception, e:
            if self.flags["verbose"]:
                print "Exception: %s, %s, %s" % \
                    (sys.exc_info()[0], sys.exc_info()[1], 
                     traceback.format_tb(sys.exc_info()[2]))
            log_completion(self.host, self.port, self.outputbuffer, e)
            self.write_output(stdout, stderr)
        try:
            os.kill(-child.pid, signal.SIGKILL)
            child.poll()
        except: pass
        self.sem.release()

    def write_output(self, stdout, stderr):
        if self.flags["outdir"]:
            pathname = "%s/%s" % (self.flags["outdir"], self.host)
            f = open(pathname, "w")
            self.write_wrap(f.fileno(), stdout.getvalue())
            f.close()
        if self.flags["errdir"]:
            pathname = "%s/%s" % (self.flags["errdir"], self.host)
            f = open(pathname, "w")
            self.write_wrap(f.fileno(), stderr.getvalue())
            f.close()

# Thread-safe queue with a single item: num completed threads
completed = Queue.Queue()
completed.put(0)
def log_completion(host, port, output, exception=None):
    # Increment the count of complete ops. This will
    # drain the queue, causing subsequent calls of this
    # method to block.
    n = completed.get() + 1
    try:
        tstamp = time.asctime().split()[3] # Current time
        if color.has_colors(sys.stdout):
            progress = color.c("[%s]" % color.B(n))
            success = color.g("[%s]" % color.B("SUCCESS"))
            failure = color.r("[%s]" % color.B("FAILURE"))
            exc = color.r(color.B(str(exception)))
        else:
            progress = "[%s]" % n
            success = "[SUCCESS]"
            failure = "[FAILURE]"
            exc = str(exception)
        if exception is not None:
            print progress, tstamp, failure, host, port, exc
        else:
            print progress, tstamp, success, host, port
        if output:
            print output,
        sys.stdout.flush()
    finally:
        # Update the count of complete ops. This will re-fill
        # the queue, allowing other threads to continue with
        # output.
        completed.put(n)
