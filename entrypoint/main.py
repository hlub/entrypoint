#!/usr/bin/env python3.7
# -*- coding: utf-8 -*-

"""Entrypoint main routine"""

import logging
import argparse
import os
import sys
import traceback
from jinja2.exceptions import TemplateSyntaxError
import yaml
from yaml.scanner import ScannerError
from . import __version__ as version
from .hooks import Hooks
from . import templates
from . import dumb_init

log = logging.getLogger(__name__)


def exec_command(variables, options):
    """Replace the current entrypoint process with the actual command.
    Even the commandline arguments of the specified command are treated as
    templates.
    """
    args = [options.command] + options.command_args
    args = [templates.render_string(arg, variables) for arg in args]
    if options.command:
        os.execvp(args[0], args)
        # if this point is reached, exec failed, so we should exit nonzero
        log.error("Exec system call failed to replace the program")
        sys.exit(2)


def collect_variables(options):
    """Return a dict of variables collected from the specified YAML
    configuration and environment.
    """
    variables = {}
    if os.path.exists(options.variables_file):
        if os.path.isdir(options.variables_file):
            raise RuntimeError(
                "Problem opening configuration volume "
                "`variables.yml`! Please make sure that you "
                "provided a valid file path."
            )
        with open(options.variables_file) as stream:
            variables = yaml.safe_load(stream) or {}
    # Update variables from environment
    variables.update(os.environ)
    return variables


def parse_args(args=None):
    """Parse commandline"""
    parser = argparse.ArgumentParser(
        usage="%(prog)s [OPTIONS] [--] COMMAND [ARGS...]",
        description="Render a directory hierarchy "
        "of templates and execute a command.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="verbose log output"
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="output only pure errors"
    )
    parser.add_argument(
        "--no-init",
        dest="dumb_init",
        default=True,
        action="store_false",
        help="disable dumb init functionality",
    )
    parser.add_argument(
        "--no-setsid",
        dest="use_setsid",
        default=True,
        action="store_false",
        help="omit use of setsid system call",
    )
    parser.add_argument(
        "-r",
        "--rewrite",
        metavar="SOURCE_SIG:DEST_SIG",
        dest="rewrites",
        default=[],
        action="append",
        help="specify signal rewrites using the signal names",
    )
    parser.add_argument(
        "-V",
        "--variables",
        metavar="PATH",
        dest="variables_file",
        default="/variables.yml",
        help="optional YAML file containing template variables",
    )
    parser.add_argument(
        "-t",
        "--templates",
        metavar="PATH",
        dest="template_root",
        default="/templates",
        help="directory structure containing template files",
    )
    parser.add_argument(
        "-j",
        "--jinja",
        metavar="PATH",
        dest="jinja_root",
        default="/jinja",
        help="root directory for jinja utility templates, "
        "which are not directly rendered but may be "
        "included within another template",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="OUTPUT",
        dest="output_root",
        default="/",
        help="output directory",
    )
    parser.add_argument(
        "-H",
        "--hooks",
        metavar="PATH",
        dest="hooks_root",
        default="/entrypoint_hooks",
        help="directory containing entrypoint hooks " "to run before the command",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="Entrypoint version {}".format(version),
        help="print version information",
    )
    parser.add_argument(
        "command",
        metavar="COMMAND [ARGS...]",
        help="the command to execute after preparations",
    )
    parser.add_argument("command_args", nargs="*", help=argparse.SUPPRESS)
    parser.epilog = """
        First, variables are read from the YAML file VARIABLES and from the
        environment, the latter overriding the former.

        Then, pre-hook functions are called from the hooks directory.
        It is possible to modify the configuration parameters for instance.

        Second, all templates in the TEMPLATES directory are rendered into the
        OUTPUT directory, maintaining the file hierarchy.(For example,
        TEMPLATES/some/file.txt will be rendered as OUTPUT/some/file.txt.)

        Then, any post-hook functions in the hooks directory are run.

        Finally, the COMMAND is executed. Template variables can also be used in
        the command and its arguments. Add '--' before the command if any ARGS
        start with '-'.
    """
    return parser.parse_args(args)


def print_jinja_error(exc):
    """Pretty proitn a template syntax error with a significant piece of
    source.
    """
    print(
        "Jinja syntax error in {}:{}: {}".format(exc.filename, exc.lineno, exc.message)
    )
    with open(exc.filename, "r") as template_file:
        lines = template_file.readlines()
        begin, end = max(0, exc.lineno - 5), min(exc.lineno + 5, len(lines))
        print("... lines {} - {} ...".format(begin + 1, end))
        for i, line in enumerate(lines[begin:end]):
            print(line.rstrip(), end="")
            if i == exc.lineno - 1:
                print("  <=====")
            else:
                print()


def print_exception():
    """Print nicer template and YAML parse errors."""
    exc_type, exc_value, exc_tb = sys.exc_info()
    tb = exc_tb
    while tb is not None:
        if tb.tb_frame.f_code.co_name == "top-level template code":
            error = traceback.format_exception(exc_type, exc_value, tb)
            error[0] = "Error rendering templates:\n"
            for line in error:
                sys.stderr.write(line)
            break
        tb = tb.tb_next
    else:
        if exc_type == ScannerError:
            log.error(exc_value)
        else:
            traceback.print_exception(exc_type, exc_value, exc_tb)


def main(args=None):
    """Main function, either call with arguments or use sys.argv as default."""
    try:
        options = parse_args(args)
        loglevel = logging.INFO
        if options.verbose:
            loglevel = logging.DEBUG
        elif options.quiet:
            loglevel = logging.ERROR
        root_logger = logging.getLogger()
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(loglevel)
        formatter = logging.Formatter("%(levelname)s: %(message)s")
        if loglevel == logging.DEBUG:
            # Use more verbose format when debugging
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)
        root_logger.setLevel(loglevel)

        if not os.environ.get("SKIP_ENTRYPOINT"):
            hooks = Hooks(options)
            variables = collect_variables(options)
            hooks.run_prehooks(variables)
            templates.process_templates(
                variables,
                output_root=options.output_root,
                template_root=options.template_root,
                jinja_root=options.jinja_root,
            )
            hooks.run_posthooks(variables)
        else:
            log.debug("SKIP_ENTRYPOINT is set, skipping entrypoint")
            variables = {}

        if options.dumb_init:
            dumb_init.init(
                map(lambda arg: arg.split(":"), options.rewrites),
                use_setsid=options.use_setsid,
            )

        exec_command(variables, options)
    except TemplateSyntaxError as err:
        print_jinja_error(err)
        sys.exit(1)
    except Exception:
        print_exception()
        sys.exit(1)


if __name__ == "__main__":
    main()
