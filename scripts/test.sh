#!/bin/bash

set -ex

ruff check .
ruff format --check .
mypy plexy tests
pytest plexy -vv tests
