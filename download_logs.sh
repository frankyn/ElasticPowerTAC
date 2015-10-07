#!/bin/bash

IP=$1

FILES=`ssh root@$IP "ls /home/log/*tar.gz"`
for f in $FILES
do
scp "root@$IP:$f" .
done
