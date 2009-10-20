# Copyright (c) 2009, Andrew McNabb
# Copyright (c) 2003-2008, Brent N. Chun

import optparse
import os
import pwd

_DEFAULT_PARALLELISM = 32
_DEFAULT_TIMEOUT     = -1 # "infinity" by default

def common_parser():
    """
    Create a basic OptionParser with arguments common to all pssh programs.
    """
    # The "resolve" conflict handler avoids errors from the hosts option
    # conflicting with the help option.
    parser = optparse.OptionParser(conflict_handler='resolve')
    # Ensure that options appearing after the command are sent to ssh.
    parser.disable_interspersed_args()
    parser.epilog = "Example: pssh -h nodes.txt -l irb2 -o /tmp/foo uptime"

    parser.add_option('-h', '--hosts', dest='host_files', action='append',
            help='hosts file (each line "host[:port] [user]")')
    parser.add_option('-l', '--user', dest='user',
            help='username (OPTIONAL)')
    parser.add_option('-p', '--par', dest='par', type='int',
            help='max number of parallel threads (OPTIONAL)')
    parser.add_option('-o', '--outdir', dest='outdir',
            help='output directory for stdout files (OPTIONAL)')
    parser.add_option('-e', '--errdir', dest='errdir',
            help='output directory for stderr files (OPTIONAL)')
    parser.add_option('-t', '--timeout', dest='timeout', type='int',
            help='timeout (secs) (-1 = no timeout) per host (OPTIONAL)')
    parser.add_option('-O', '--options', dest='options',
            help='SSH options (OPTIONAL)')
    parser.add_option('-v', '--verbose', dest='verbose', action='store_true',
            help='turn on warning and diagnostic messages (OPTIONAL)')
    parser.add_option('-A', '--askpass', dest='askpass', action='store_true',
            help='Ask for a password (OPTIONAL)')

    return parser

def common_defaults(**kwargs):
    current_user = pwd.getpwuid(os.getuid())[0]
    defaults = dict(par=_DEFAULT_PARALLELISM, timeout=_DEFAULT_TIMEOUT,
            user=current_user)
    defaults.update(**kwargs)
    envvars = [('user', 'PSSH_USER'),
            ('par', 'PSSH_PAR'),
            ('outdir', 'PSSH_OUTDIR'),
            ('errdir', 'PSSH_ERRDIR'),
            ('timeout', 'PSSH_TIMEOUT'),
            ('options', 'PSSH_OPTIONS'),
            ('verbose', 'PSSH_VERBOSE'),
            ('print_out', 'PSSH_PRINT'),
            ('askpass', 'PSSH_ASKPASS'),
            ('inline', 'PSSH_INLINE'),
            ('recursive', 'PSSH_RECURSIVE'),
            ('archive', 'PSSH_ARCHIVE'),
            ('compress', 'PSSH_COMPRESS'),
            ('localdir', 'PSSH_LOCALDIR'),
            ]
    for option, var, in envvars:
        value = os.getenv(var)
        if value:
            defaults[option] = value

    value = os.getenv('PSSH_HOSTS')
    if value:
        defaults['host_files'] = [value]

    return defaults


def parse_args():
    parser = option_parser()
    opts, args = parser.parse_args()
    #switch to this?: if opts.timeout <= 0:
    if opts.timeout == -1:
        opts.timeout = None

    if len(args) == 0:
        parser.error('Command not specified.')

    if not opts.hosts:
        parser.error('Hosts not specified.')

    return opts, args
