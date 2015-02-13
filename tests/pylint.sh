#!/bin/sh

exec pylint --output-format=colorized --rcfile=tests/pylint.cfg tests/*.py *.py
