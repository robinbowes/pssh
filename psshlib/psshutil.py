# Copyright (c) 2009, Andrew McNabb
# Copyright (c) 2003-2008, Brent N. Chun

import fcntl
import string
import sys

HOST_FORMAT = 'Host format is [user@]host[:port] [user]'


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
        line = line.strip(string.whitespace + '#')
        if not line:
            continue
        host, port, user = parse_line(line, default_user, default_port)
        if host:
            hosts.append((host, port, user))
    return hosts

# TODO: eventually deprecate the second host field and standardize on the
# [user@]host[:port] format.
def parse_line(line, default_user, default_port):
    fields = line.split()
    if len(fields) > 2:
        sys.stderr.write('Bad line: "%s". Format should be'
                ' [user@]host[:port] [user]\n' % line)
        return None, None, None
    host_field = fields[0]
    host, port, user = parse_host(host_field, default_port=default_port)
    if len(fields) == 2:
        if user is None:
            user = fields[1]
        else:
            sys.stderr.write('User specified twice in line: "%s"\n' % line)
            return None, None, None
    if user is None:
        user = default_user
    return host, port, user


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


def set_cloexec(filelike):
    """Sets the underlying filedescriptor to automatically close on exec.

    If set_cloexec is called for all open files, then subprocess.Popen does
    not require the close_fds option.
    """
    fcntl.fcntl(filelike.fileno(), fcntl.FD_CLOEXEC, 1)
