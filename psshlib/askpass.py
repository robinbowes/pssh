#!/usr/bin/env python
# -*- Mode: python -*-

# Copyright (c) 2009, Andrew McNabb

"""Reads a password from the socket specified by the environment variable
PSSH_ASKPASS_SOCKET.  This file also contains the corresponding server
code.
"""

import os
import socket
import sys
import textwrap

def password_client():
    address = os.getenv('PSSH_ASKPASS_SOCKET')
    if not address:
        sys.stderr.write(textwrap.fill("Permission denied.  Please create"
                " SSH keys or use the -A option to provide a password."))
        sys.stderr.write('\n')
        sys.exit(1)

    sock = socket.socket(socket.AF_UNIX)
    try:
        sock.connect(address)
    except socket.error:
        _, e, _ = sys.exc_info()
        number, message = e.args
        sys.stderr.write("Couldn't bind to %s: %s.\n" % (address, message))
        sys.exit(2)

    try:
        password = sock.makefile().read()
    except socket.error:
        sys.stderr.write("Socket error.\n")
        sys.exit(3)

    print(password)


if __name__ == '__main__':
    password_client()
