#!/usr/bin/python

# Copyright (c) 2009, Andrew McNabb
# Copyright (c) 2003-2008, Brent N. Chun

import os 
import sys
import shutil
import tempfile
import time
import unittest

basedir, bin = os.path.split(os.path.dirname(os.path.abspath(sys.argv[0])))
sys.path.append("%s" % basedir)

if os.getenv("TEST_HOSTS") is None:
    raise Exception("Must define TEST_HOSTS")
g_hosts = os.getenv("TEST_HOSTS").split()

if os.getenv("TEST_USER") is None:
    raise Exception("Must define TEST_USER")
g_user = os.getenv("TEST_USER")

class PsshTest(unittest.TestCase):
    def setUp(self):
        self.outDir = tempfile.mkdtemp()
        self.errDir = tempfile.mkdtemp()

    def teardown(self):
        shutil.rmtree(self.errDir)
        shutil.rmtree(self.outDir)

    def testShortOpts(self):
        hostsFile = tempfile.NamedTemporaryFile()
        hostsFile.write("".join(map(lambda x: "%s\n" % x, g_hosts)))
        hostsFile.flush()
        cmd = "%s/bin/pssh -h %s -l %s -p 64 -o %s -e %s -t 60 -v -P -i uptime < /dev/null" % (basedir, hostsFile.name, g_user, self.outDir, self.errDir)
        rv = os.system(cmd)
        self.assertEqual(rv, 0)
        for host in g_hosts:
            stdout = open("%s/%s" % (self.outDir, host)).read()
            self.assert_(stdout.find("load average") != -1)

    def testLongOpts(self):
        hostsFile = tempfile.NamedTemporaryFile()
        hostsFile.write("".join(map(lambda x: "%s\n" % x, g_hosts)))
        hostsFile.flush()
        cmd = "%s/bin/pssh --hosts=%s --user=%s --par=64 --outdir=%s --errdir=%s --timeout=60 --verbose --print --inline uptime < /dev/null" % (basedir, hostsFile.name, g_user, self.outDir, self.errDir)
        rv = os.system(cmd)
        self.assertEqual(rv, 0)
        for host in g_hosts:
            stdout = open("%s/%s" % (self.outDir, host)).read()
            self.assert_(stdout.find("load average") != -1)

    def testStderr(self):
        hostsFile = tempfile.NamedTemporaryFile()
        hostsFile.write("".join(map(lambda x: "%s\n" % x, g_hosts)))
        hostsFile.flush()
        cmd = "%s/bin/pssh -h %s -l %s -p 64 -o %s -e %s -t 60 -v -P -i ls /foobarbaz < /dev/null" % (basedir, hostsFile.name, g_user, self.outDir, self.errDir)
        rv = os.system(cmd)
        self.assertEqual(rv, 0)
        for host in g_hosts:
            stdout = open("%s/%s" % (self.outDir, host)).read()
            self.assertEqual(stdout, "")
            stderr = open("%s/%s" % (self.errDir, host)).read()
            self.assert_(stderr.find("No such file or directory") != -1)

class PscpTest(unittest.TestCase):
    def setUp(self):
        self.outDir = tempfile.mkdtemp()
        self.errDir = tempfile.mkdtemp()

    def teardown(self):
        shutil.rmtree(self.errDir)
        shutil.rmtree(self.outDir)
        try:
            os.remove("/tmp/pssh.test")
        except OSError:
            pass

    def testShortOpts(self):
        for host in g_hosts:
            cmd = "ssh %s@%s rm -rf /tmp/pssh.test" % (g_user, host)
            rv = os.system(cmd)
            self.assertEqual(rv, 0)

        hostsFile = tempfile.NamedTemporaryFile()
        hostsFile.write("".join(map(lambda x: "%s\n" % x, g_hosts)))
        hostsFile.flush()
        cmd = "%s/bin/pscp -h %s -l %s -p 64 -o %s -e %s -t 60 /etc/hosts /tmp/pssh.test < /dev/null" % (basedir, hostsFile.name, g_user, self.outDir, self.errDir)
        rv = os.system(cmd)
        self.assertEqual(rv, 0)
        for host in g_hosts:
            cmd = "ssh %s@%s cat /tmp/pssh.test" % (g_user, host)
            data = os.popen(cmd).read()
            self.assertEqual(data, open("/etc/hosts").read())

    def testLongOpts(self):
        for host in g_hosts:
            cmd = "ssh %s@%s rm -rf /tmp/pssh.test" % (g_user, host)
            rv = os.system(cmd)
            self.assertEqual(rv, 0)

        hostsFile = tempfile.NamedTemporaryFile()
        hostsFile.write("".join(map(lambda x: "%s\n" % x, g_hosts)))
        hostsFile.flush()
        cmd = "%s/bin/pscp --hosts=%s --user=%s --par=64 --outdir=%s --errdir=%s --timeout=60 /etc/hosts /tmp/pssh.test < /dev/null" % (basedir, hostsFile.name, g_user, self.outDir, self.errDir)
        rv = os.system(cmd)
        self.assertEqual(rv, 0)
        for host in g_hosts:
            cmd = "ssh %s@%s cat /tmp/pssh.test" % (g_user, host)
            data = os.popen(cmd).read()
            self.assertEqual(data, open("/etc/hosts").read())

    def testRecursive(self):
        for host in g_hosts:
            cmd = "ssh %s@%s rm -rf /tmp/pssh.test" % (g_user, host)
            rv = os.system(cmd)
            self.assertEqual(rv, 0)

        hostsFile = tempfile.NamedTemporaryFile()
        hostsFile.write("".join(map(lambda x: "%s\n" % x, g_hosts)))
        hostsFile.flush()
        cmd = "%s/bin/pscp -r -h %s -l %s -p 64 -o %s -e %s -t 60 /etc/init.d /tmp/pssh.test < /dev/null" % (basedir, hostsFile.name, g_user, self.outDir, self.errDir)
        rv = os.system(cmd)
        self.assertEqual(rv, 0)
        files = os.popen("ls -R /etc/init.d | sed 1d | sort").read().strip()
        for host in g_hosts:
            cmd = "ssh %s@%s ls -R /tmp/pssh.test | sed 1d | sort" % (g_user, host)
            data = os.popen(cmd).read().strip()
            self.assertEqual(data, files)

class PslurpTest(unittest.TestCase):
    def setUp(self):
        self.outDir = tempfile.mkdtemp()
        self.errDir = tempfile.mkdtemp()

    def teardown(self):
        shutil.rmtree(self.errDir)
        shutil.rmtree(self.outDir)

    def testShortOpts(self):
        if os.path.exists("/tmp/pssh.test"):
            try:
                os.remove("/tmp/pssh.test")
            except OSError:
                shutil.rmtree("/tmp/pssh.test")

        hostsFile = tempfile.NamedTemporaryFile()
        hostsFile.write("".join(map(lambda x: "%s\n" % x, g_hosts)))
        hostsFile.flush()
        cmd = "%s/bin/pslurp -L /tmp/pssh.test -h %s -l %s -p 64 -o %s -e %s -t 60 /etc/hosts hosts < /dev/null" % (basedir, hostsFile.name, g_user, self.outDir, self.errDir)
        rv = os.system(cmd)
        self.assertEqual(rv, 0)

        for host in g_hosts:
            cmd = "ssh %s@%s cat /etc/hosts" % (g_user, host)
            data = os.popen(cmd).read()
            self.assertEqual(data, open("/tmp/pssh.test/%s/hosts" % host).read())

    def testLongOpts(self):
        if os.path.exists("/tmp/pssh.test"):
            try:
                os.remove("/tmp/pssh.test")
            except OSError:
                shutil.rmtree("/tmp/pssh.test")

        hostsFile = tempfile.NamedTemporaryFile()
        hostsFile.write("".join(map(lambda x: "%s\n" % x, g_hosts)))
        hostsFile.flush()
        cmd = "%s/bin/pslurp --localdir=/tmp/pssh.test --hosts=%s --user=%s --par=64 --outdir=%s --errdir=%s --timeout=60 /etc/hosts hosts < /dev/null" % (basedir, hostsFile.name, g_user, self.outDir, self.errDir)
        rv = os.system(cmd)
        self.assertEqual(rv, 0)

        for host in g_hosts:
            cmd = "ssh %s@%s cat /etc/hosts" % (g_user, host)
            data = os.popen(cmd).read()
            self.assertEqual(data, open("/tmp/pssh.test/%s/hosts" % host).read())

    def testRecursive(self):
        if os.path.exists("/tmp/pssh.test"):
            try:
                os.remove("/tmp/pssh.test")
            except OSError:
                shutil.rmtree("/tmp/pssh.test")

        hostsFile = tempfile.NamedTemporaryFile()
        hostsFile.write("".join(map(lambda x: "%s\n" % x, g_hosts)))
        hostsFile.flush()
        cmd = "%s/bin/pslurp -r -L /tmp/pssh.test -h %s -l %s -p 64 -o %s -e %s -t 60 /etc/init.d init.d < /dev/null" % (basedir, hostsFile.name, g_user, self.outDir, self.errDir)
        rv = os.system(cmd)
        self.assertEqual(rv, 0)

        for host in g_hosts:
            cmd = "ssh %s@%s ls -R /etc/init.d | sed 1d | sort" % (g_user, host)
            data = os.popen(cmd).read()
            self.assertEqual(data, os.popen("ls -R /tmp/pssh.test/%s/init.d | sed 1d | sort" % host).read())

class PrsyncTest(unittest.TestCase):
    def setUp(self):
        self.outDir = tempfile.mkdtemp()
        self.errDir = tempfile.mkdtemp()

    def teardown(self):
        shutil.rmtree(self.errDir)
        shutil.rmtree(self.outDir)

    def testShortOpts(self):
        for host in g_hosts:
            cmd = "ssh %s@%s rm -rf /tmp/pssh.test" % (g_user, host)
            rv = os.system(cmd)
            self.assertEqual(rv, 0)

        hostsFile = tempfile.NamedTemporaryFile()
        hostsFile.write("".join(map(lambda x: "%s\n" % x, g_hosts)))
        hostsFile.flush()
        cmd = "%s/bin/prsync -h %s -l %s -p 64 -o %s -e %s -t 60 -a -z /etc/hosts /tmp/pssh.test < /dev/null" % (basedir, hostsFile.name, g_user, self.outDir, self.errDir)
        rv = os.system(cmd)
        self.assertEqual(rv, 0)
        for host in g_hosts:
            cmd = "ssh %s@%s cat /tmp/pssh.test" % (g_user, host)
            data = os.popen(cmd).read()
            self.assertEqual(data, open("/etc/hosts").read())

    def testLongOpts(self):
        for host in g_hosts:
            cmd = "ssh %s@%s rm -rf /tmp/pssh.test" % (g_user, host)
            rv = os.system(cmd)
            self.assertEqual(rv, 0)

        hostsFile = tempfile.NamedTemporaryFile()
        hostsFile.write("".join(map(lambda x: "%s\n" % x, g_hosts)))
        hostsFile.flush()
        cmd = "%s/bin/prsync --hosts=%s --user=%s --par=64 --outdir=%s --errdir=%s --timeout=60 --archive --compress /etc/hosts /tmp/pssh.test < /dev/null" % (basedir, hostsFile.name, g_user, self.outDir, self.errDir)
        rv = os.system(cmd)
        self.assertEqual(rv, 0)
        for host in g_hosts:
            cmd = "ssh %s@%s cat /tmp/pssh.test" % (g_user, host)
            data = os.popen(cmd).read()
            self.assertEqual(data, open("/etc/hosts").read())

    def testRecursive(self):
        for host in g_hosts:
            cmd = "ssh %s@%s rm -rf /tmp/pssh.test" % (g_user, host)
            rv = os.system(cmd)
            self.assertEqual(rv, 0)

        hostsFile = tempfile.NamedTemporaryFile()
        hostsFile.write("".join(map(lambda x: "%s\n" % x, g_hosts)))
        hostsFile.flush()
        cmd = "%s/bin/prsync -r -h %s -l %s -p 64 -o %s -e %s -t 60 -a -z /etc/init.d/ /tmp/pssh.test < /dev/null" % (basedir, hostsFile.name, g_user, self.outDir, self.errDir)
        rv = os.system(cmd)
        self.assertEqual(rv, 0)
        files = os.popen("ls -R /etc/init.d | sed 1d | sort").read().strip()
        for host in g_hosts:
            cmd = "ssh %s@%s ls -R /tmp/pssh.test | sed 1d | sort" % (g_user, host)
            data = os.popen(cmd).read().strip()
            self.assertEqual(data, files)

class PnukeTest(unittest.TestCase):
    def setUp(self):
        self.outDir = tempfile.mkdtemp()
        self.errDir = tempfile.mkdtemp()

    def teardown(self):
        shutil.rmtree(self.errDir)
        shutil.rmtree(self.outDir)

    def testShortOpts(self):
        hostsFile = tempfile.NamedTemporaryFile()
        hostsFile.write("".join(map(lambda x: "%s\n" % x, g_hosts)))
        hostsFile.flush()
        cmd = "%s/bin/pssh -h %s -l %s -p 64 -o %s -e %s -t 60 -v sleep 60 < /dev/null &" % (basedir, hostsFile.name, g_user, self.outDir, self.errDir)
        os.system(cmd)
        time.sleep(5)

        cmd = "%s/bin/pnuke -h %s -l %s -p 64 -o %s -e %s -t 60 -v sleep < /dev/null" % (basedir, hostsFile.name, g_user, self.outDir, self.errDir)
        print cmd
        rv = os.system(cmd)
        self.assertEqual(rv, 0)

    def testLongOpts(self):
        hostsFile = tempfile.NamedTemporaryFile()
        hostsFile.write("".join(map(lambda x: "%s\n" % x, g_hosts)))
        hostsFile.flush()
        cmd = "%s/bin/pssh --hosts=%s --user=%s --par=64 --outdir=%s --errdir=%s --timeout=60 --verbose sleep 60 < /dev/null &" % (basedir, hostsFile.name, g_user, self.outDir, self.errDir)
        os.system(cmd)
        time.sleep(5)

        cmd = "%s/bin/pnuke --hosts=%s --user=%s --par=64 --outdir=%s --errdir=%s --timeout=60 --verbose sleep < /dev/null" % (basedir, hostsFile.name, g_user, self.outDir, self.errDir)
        print cmd
        rv = os.system(cmd)
        self.assertEqual(rv, 0)

if __name__ == '__main__':
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(PsshTest, "test"))
    suite.addTest(unittest.makeSuite(PscpTest, "test"))
    suite.addTest(unittest.makeSuite(PslurpTest, "test"))
    suite.addTest(unittest.makeSuite(PrsyncTest, "test"))
    suite.addTest(unittest.makeSuite(PnukeTest, "test"))
    unittest.TextTestRunner().run(suite)
