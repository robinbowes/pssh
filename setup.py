from setuptools import setup, find_packages
import os
setup(
    name = "pssh",
    version = "1.3.2",
    author = "Brent N. Chun",
    url = "http://www.theether.org/pssh/",
    license = "BSD",
    packages = find_packages(),
    scripts = [os.path.join("bin", p) for p in ["pssh", "pnuke", "prsync", "pslurp", "pscp"]]
    )
