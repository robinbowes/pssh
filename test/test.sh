#!/bin/sh

# Test data

mkdir /tmp/pssh.test.data
cp /etc/hosts /tmp/pssh.test.data/1.txt
cp /etc/hosts /tmp/pssh.test.data/2.txt
cp /etc/hosts /tmp/pssh.test.data/3.txt

# Tests

pssh -h ips.txt -l bnc -p 64 -o /tmp/pssh.test.foo1.good \
     -e /tmp/pssh.test.bar1.good -t 60 ls /
pssh -h ips.txt -l bnc -p 64 -o /tmp/pssh.test.foo1.bad \
     -e /tmp/pssh.test.bar1.bad -t 60 ls /xyz

pscp -r -h ips.txt -l bnc -p 64 -o /tmp/pssh.test.foo2.good \
     -e /tmp/pssh.test.bar2.good -t 120 /tmp/pssh.test.data \
     /tmp/pssh.test.data.remote
pscp -r -h ips.txt -l bnc -p 64 -o /tmp/pssh.test.foo2.bad \
     -e /tmp/pssh.test.bar2.bad -t 120 /tmp/pssh.test.data \
     /etc

cp /etc/hosts /tmp/pssh.test.data/4.txt
prsync -r -h ips.txt -l bnc -p 64 -o /tmp/pssh.test.foo3.good \
       -e /tmp/pssh.test.bar3.good -t 120 /tmp/pssh.test.data/ \
       /tmp/pssh.test.data.remote/
prsync -r -h ips.txt -l bnc -p 64 -o /tmp/pssh.test.foo3.bad \
       -e /tmp/pssh.test.bar3.bad -t 120 /tmp/pssh.test.data/ /etc/

pslurp -r -L /tmp/pssh.test.baz4.good -h ips.txt -l bnc -p 64 \
       -o /tmp/pssh.test.foo4.good -e /tmp/pssh.test.bar4.good \
       -t 120 /tmp/pssh.test.data.remote data
pslurp -r -L /tmp/pssh.test.baz4.bad -h ips.txt -l bnc -p 64 \
       -o /tmp/pssh.test.foo4.bad -e /tmp/pssh.test.bar4.bad -t 120 /xyz data

# Clean up

#rm -rf /tmp/pssh.test.*
