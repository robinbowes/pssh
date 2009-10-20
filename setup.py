from setuptools import setup, find_packages
import os

long_description = """PSSH (Parallel SSH) provides parallel versions of OpenSSH and related tools, including pssh, pscp, prsync, pnuke, and pslurp.  The project includes psshlib which can be used within custom applications."""

setup(
    name = "pssh",
    version = "2.0",
    author = "Andrew McNabb",
    author_email = "amcnabb@mcnabbs.org",
    url = "http://code.google.com/p/parallel-ssh/",
    description = "Parallel version of OpenSSH and related tools",
    long_description = long_description,
    license = "BSD",
    platforms = ['linux'],

    classifiers = [
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: BSD License",
        "Operating System :: POSIX",
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Clustering",
        "Topic :: System :: Networking",
        "Topic :: System :: Systems Administration",
        ],

    packages = find_packages(),
    scripts = [os.path.join("bin", p) for p in ["pssh", "pnuke", "prsync", "pslurp", "pscp"]]
    )
