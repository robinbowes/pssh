import re
import sys

def read_hosts(pathname):
    """
    Read hostfile with lines of the form: host[:port] [login]. Return
    three arrays: hosts, ports, and users.  These can be used directly
    for all ssh-based commands (e.g., ssh, scp, rsync -e ssh, etc.)
    """
    f = open(pathname)
    lines = f.readlines()
    lines = map(lambda x: x.strip(), lines)
    addrs = []
    hosts = []
    ports = []
    users = []
    for line in lines:
        # Skip blank lines or lines starting with #
        if re.match("^\s+$", line) or re.match("^\s*#", line) or len(line) == 0:
            continue
        fields = re.split("\s", line)
        if len(fields) == 1:
            addrs.append(line)
            users.append(None)
        elif len(fields) == 2:
            addrs.append(fields[0])
            users.append(fields[1])
        else:
            print "Bad line. Must be host[:port] [login]"
            sys.exit(3)
    f.close()
    for i in range(len(addrs)):
        addr = addrs[i]
        if re.search(":", addrs[i]):
            host, port = re.split(":", addr)
            hosts.append(host)
            ports.append(int(port))
        else:
            hosts.append(addr)
            ports.append(22)
    return hosts, ports, users

def patch_users(hosts, ports, users, user):
    """Fill in missing entries in users array with specified user"""
    for i in range(len(hosts)):
        if not users[i] and user:
            users[i] = user
        elif not users[i] and not user:
            print "User not specified for %s:%d" % (hosts[i], ports[i])
            sys.exit(3)
