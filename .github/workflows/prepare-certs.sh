#!/bin/sh -x
#ls -la $MAILU_BASE
mkdir -p $MAILU_BASE/certs
cp ./tests/certs/* $MAILU_BASE/certs
chmod 600 $MAILU_BASE/certs/*

#docker volume create --name $1
#docker run -d --rm --name dummy-$1 -v $1:/mailu alpine tail -f /dev/null
#docker exec dummy-$1 mkdir -p /mailu/certs
#for i in tests/certs/*
#do
#	docker cp $i dummy-$1:/mailu/$(basename $i)
#done
#docker exec dummy-$1 sh -c 'chmod 600 /mailu/*'
#docker stop dummy-$1
