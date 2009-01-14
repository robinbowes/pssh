#!/usr/bin/env python
# -*- Mode: python -*-
#
# Reads a password from the socket specified by the environment variable
# PSSH_ASKPASS_SOCKET.  This file also contains the corresponding server
# code.
#
# Created: 14 January 2009

import errno
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
        self.socketmap = {}
        self.buffermap = {}

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
            number, string = e.args
            if number == errno.EINTR:
                return
            else:
                # TODO: print an error message here?
                self.sock.close()
        fd = conn.fileno()
        iomap.register(fd, self.handle_write, write=True)
        self.socketmap[fd] = conn
        self.buffermap[fd] = self.password

    def handle_write(self, fd, event, iomap):
        buffer = self.buffermap[fd]
        conn = self.socketmap[fd]
        try:
            bytes_written = conn.send(buffer)
        except socket.error, e:
            number, string = e.args
            if number == errno.EINTR:
                return
            else:
                self.close_socket(fd, iomap)

        buffer = buffer[bytes_written:]
        if buffer:
            self.buffermap[fd] = buffer
        else:
            self.close_socket(fd, iomap)

    def close_socket(self, fd, iomap):
        iomap.unregister(fd)
        self.socketmap[fd].close()
        del self.socketmap[fd]
        del self.buffermap[fd]

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

    try:
        password = sock.makefile().read()
    except socket.error, e:
        print >>sys.stderr, "Socket error."
        sys.exit(3)

    print password


if __name__ == '__main__':
    password_client()
