from setuptools import setup, find_packages
import os
setup(
    name = "pssh",
    version = "1.4.3",
    author = "Andrew McNabb",
    url = "http://code.google.com/p/parallel-ssh/",
    license = "BSD",
    packages = find_packages(),
    scripts = [os.path.join("bin", p) for p in ["pssh", "pnuke", "prsync", "pslurp", "pscp"]]
    )
