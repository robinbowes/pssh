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
    if not pathnames:
        return lines
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
            sys.stderr.write("Bad line. Must be host[:port] [login]\n")
            sys.exit(3)
        addr_fields = addr.split(':')
        if len(addr_fields) == 1:
            host = addr
            port = default_port
        elif len(addr_fields) == 2:
            host, port = addr_fields
        else:
            sys.stderr.write("Bad line. Must be host[:port] [login]\n")
            sys.exit(3)
        hosts.append((host, port, user))
    return hosts

def parse_host(host, default_user=None, default_port=None):
    """Parses host entries of the form "[user@]host[:port]"."""
    # TODO: when we stop supporting Python 2.4, switch to using str.partition.
    user = default_user
    port = default_port
    if '@' in host:
        user, host = host.split('@', 1)
    if ':' in host:
        host, port = host.rsplit(':', 1)
    return (host, port, user)
