#!/bin/bash

set -ex

flake8
mypy --check-untyped-defs plexy
mypy --check-untyped-defs tests
pytest plexy -vv tests
