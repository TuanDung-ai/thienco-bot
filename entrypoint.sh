#!/bin/bash
exec gunicorn -w 1 -b :8080 main:app
#🔧 Add entrypoint.sh để khởi chạy gunicorn đúng cách
