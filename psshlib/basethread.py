import color, cStringIO, fcntl, os, select, signal, sys, threading, time, Queue
from subprocess import Popen, PIPE

class BaseThread(threading.Thread):
    def __init__(self, host, port, cmd, flags, sem, input=None):
        threading.Thread.__init__(self)
        self.host = host
        self.port = port
        self.cmd = cmd
        self.flags = flags
        self.sem = sem
        self.input = input
        self.outputbuffer = ''

    def run(self):
        done = None
        stdout = cStringIO.StringIO()
        stderr = cStringIO.StringIO()
        try:
            child = Popen([self.cmd], stderr=PIPE, stdin=PIPE, stdout=PIPE,
                          close_fds=True, preexec_fn=os.setsid, shell=True)
            cstdout = child.stdout
            cstderr = child.stderr
            cstdin = child.stdin
            if self.input:
                cstdin.write(self.input)
                cstdin.close()
                del self.input # Throw away stdin's input, since we don't need it
            iomap = { cstdout : stdout, cstderr : stderr }
            fcntl.fcntl(cstdout.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)
            fcntl.fcntl(cstderr.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)
            start = time.time()
            status = -1 # Set status to -1 for other errors (timeout, etc.)
            while 1:
                timeout = self.flags["timeout"] - (time.time() - start)
                if timeout <= 0:
                    raise Exception("Timeout")
                r, w, e = select.select([ cstdout, cstderr ], [], [], timeout)
                try:
                    for f in r:
                        chunk = f.read()
                        if len(chunk) == 0:
                            done = 1
                        iomap[f].write(chunk)                    
                        if self.flags.has_key("print") and self.flags["print"]:
                            to_write = "%s: %s" % (self.host, chunk)
                            sys.stdout.write(to_write)
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
            log_completion(self.host, self.port, self.outputbuffer, e)
            self.write_output(stdout, stderr)
        try:
            os.kill(-child.pid, signal.SIGKILL)
        except: pass
        self.sem.release()

    def write_output(self, stdout, stderr):
        if self.flags["outdir"]:
            pathname = "%s/%s" % (self.flags["outdir"], self.host)
            open(pathname, "w").write(stdout.getvalue())
        if self.flags["errdir"]:
            pathname = "%s/%s" % (self.flags["errdir"], self.host)
            open(pathname, "w").write(stderr.getvalue())

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
            print progress, tstamp, failure, host, exc
        else:
            print progress, tstamp, success, host
        if output:
            print output,
        sys.stdout.flush()
    finally:
        # Update the count of complete ops. This will re-fill
        # the queue, allowing other threads to continue with
        # output.
        completed.put(n)
