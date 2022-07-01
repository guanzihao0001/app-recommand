#!/bin/sh

supervisord -c supervisord.conf

tail -f /dev/null
