#!/usr/bin/env python3
"""
Apply operation to bitmap font
(c) 2019--2021 Rob Hagemans, licence: https://opensource.org/licenses/MIT
"""

import sys
import argparse
import logging

import monobit
from monobit.scripting import main


# parse command line
parser = argparse.ArgumentParser()

parser.add_argument('--infile', type=str, default='')
parser.add_argument('--outfile', type=str, default='')

parser.add_argument(
    '--overwrite', action='store_true',
    help='overwrite existing output file'
)
parser.add_argument(
    '--debug', action='store_true',
    help='show debugging output'
)

subparsers = parser.add_subparsers(dest='operation')
for name, func in monobit.operations.items():
    sub = subparsers.add_parser(name, help=func.script_args.doc)
    for arg, _type, doc in func.script_args:
        if _type == bool:
            sub.add_argument(f'--{arg}', dest=arg, help=doc, action='store_true')
            sub.add_argument(f'--no-{arg}', dest=arg, help=f'unset --{arg}', action='store_false')
        else:
            sub.add_argument(f'--{arg}', type=_type, help=doc)

# force error on unknown arguments
args = parser.parse_args()

# find out which operation we're asked to perform
operation = monobit.operations[args.operation]

with main(args, logging.WARNING):

    # load
    fonts = monobit.load(args.infile or sys.stdin)

    # modify
    fonts = tuple(
        operation(_font, **operation.script_args.pick(args))
        for _font in fonts
    )

    # save
    monobit.save(fonts, args.outfile or sys.stdout, overwrite=args.overwrite)
