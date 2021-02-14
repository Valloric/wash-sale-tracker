#!/usr/bin/sh

set -ex

python lots_test.py
python wash_test.py
python run_integ_tests.py
