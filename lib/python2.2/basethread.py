import cStringIO, fcntl, os, popen2, select, signal, sys, threading, time

class BaseThread(threading.Thread):
    def __init__(self, host, port, cmd, flags, sem):
        threading.Thread.__init__(self)
        self.host = host
        self.port = port
        self.cmd = cmd
        self.flags = flags
        self.sem = sem

    def run(self):
        done = None
        stdout = cStringIO.StringIO()
        stderr = cStringIO.StringIO()
        try:
            child = popen2.Popen3(self.cmd, capturestderr=1)
            cstdout = child.fromchild
            cstderr = child.childerr
            iomap = { cstdout : stdout, cstderr : stderr }
            fcntl.fcntl(cstdout.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)
            fcntl.fcntl(cstderr.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)
            start = time.time()
            status = -1 # Set status to -1 for other errors (timeout, etc.)
            while 1:
                timeout = self.flags["timeout"] - (time.time() - start)
                if timeout <= 0:
                    raise "Timeout on %s:%d" % (self.host, self.port)
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
                    if done:
                        break
                except:
                    os.kill(child.pid, signal.SIGKILL)
                    raise
            status = child.wait() # Shouldn't block (just to get status)
            if status:
                raise "Error on %s:%d (status %d)" % \
                      (self.host, self.port, status)
            self.write_output(stdout, stderr)
            print "Success on %s:%d" % (self.host, self.port)
            sys.stdout.flush()
        except:
            print "Error on %s:%d" % (self.host, self.port)
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
