#!/bin/bash
exec gunicorn -w 1 -b :8080 main:app

