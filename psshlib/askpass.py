#!/usr/bin/env python
# -*- Mode: python -*-
#
# Reads a password from the socket specified by the environment variable
# PSSH_ASKPASS_SOCKET.  This file also contains the corresponding server
# code.
#
# Created: 14 January 2009

import getpass
import os
import socket
import sys
import textwrap

class PasswordServer(object):
    """Listens on a UNIX domain socket for password requests."""
    def __init__(self):
        self.sock = None
        self.tempdir = None
        self.address = None

    def ask(self):
        message = ('Warning: do not enter your password if anyone else has'
                'superuser privileges or access to your account.')
        print textwrap.fill(message)
            
        self.password = getpass.getpass()

    def start(self, iomap, backlog):
        """Creates a socket and starts listening.

        The specified backlog should be the max number of clients connecting
        at once.
        """
        # Note that according to the docs for mkdtemp, "The directory is
        # readable, writable, and searchable only by the creating user."
        self.tempdir = tempfile.mkdtemp(prefix='pssh')
        self.address = os.path.join(self.tempdir, 'pssh_askpass_socket')
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.bind(self.address)
        self.sock.listen(backlog)
        iomap.register(self.sock.fileno(), self.handle_listen, read=True)

    def handle_listen(self, fd, event, iomap):
        try:
            conn, address = self.sock.accept()
        except socket.error, e:
            # FIXME
            return
        iomap.register(conn.fileno(), self.handle_write, write=True)

    def handle_write(self, fd, event, iomap):
        pass

    def __del__(self):
        if self.sock:
            # FIXME Delete it!
            pass


def password_client():
    address = os.getenv('PSSH_ASKPASS_SOCKET')
    if not address:
        print >>sys.stderr, "Environment variable PSSH_ASKPASS_SOCKET not set."
        sys.exit(1)

    sock = socket.socket(socket.AF_UNIX)
    try:
        sock.bind(address)
    except socket.error, e:
        print >>sys.stderr, "Couldn't bind to socket at %s." % address
        sys.exit(2)

    password = sock.makefile().read()
    print password


if __name__ == '__main__':
    password_client()
