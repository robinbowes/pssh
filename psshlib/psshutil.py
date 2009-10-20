# Copyright (c) 2009, Andrew McNabb
# Copyright (c) 2003-2008, Brent N. Chun

import re
import sys

def read_hosts(pathnames, default_user=None, default_port=None):
    """
    Read hostfiles specified by the given pathnames with lines of the form:
    host[:port] [login]. Return three arrays: hosts, ports, and users.  These
    can be used directly for all ssh-based commands (e.g., ssh, scp, rsync -e
    ssh, etc.)
    """
    lines = []
    for pathname in pathnames:
        f = open(pathname)
        for line in f:
            lines.append(line.strip())
        f.close()
    hosts = []
    for line in lines:
        # Skip blank lines or lines starting with #
        if not line or line.startswith('#'):
            continue
        fields = line.split()
        if len(fields) == 1:
            addr = line
            user = default_user
        elif len(fields) == 2:
            addr, user = fields
        else:
            print "Bad line. Must be host[:port] [login]"
            sys.exit(3)
        addr_fields = addr.split(':')
        if len(addr_fields) == 1:
            host = addr
            port = default_port
        elif len(addr_fields) == 2:
            host, port = addr_fields
        else:
            print "Bad line. Must be host[:port] [login]"
            sys.exit(3)
        hosts.append((host, port, user))
    return hosts

