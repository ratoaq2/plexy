#!/bin/bash

set -ex

uv run ruff check .
uv run ruff format --check .
uv run mypy plexy tests
uv run pytest plexy -vv tests
