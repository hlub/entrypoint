"""Enrich the global functions and variables of Jinja templates.

Add any functions or variables into the scope of this module.
Remember to prefix every internal name with underscore!
"""

import builtins as _builtins
import glob as _glob
from jinja2 import contextfunction as _contextfunction, defaults as _defaults

min = _builtins.min
max = _builtins.max
abs = _builtins.abs
all = _builtins.all
any = _builtins.any
round = _builtins.round
# Python's zip returns a generator object. in Jinja we want a list:
zip = lambda *args: list(_builtins.zip(*args))


@_contextfunction
def context(ctx):
    """Return the whole top-level context of the Jinja rendering as a dict.
    This allows iteration over all available data.
    """
    defaults = list(globals().keys()) + list(_defaults.DEFAULT_NAMESPACE.keys())
    return {k: v for k, v in ctx.items() if k not in defaults}


def glob(pattern):
    return _glob.glob(pattern)


def iglob(pattern):
    return _glob.iglob(pattern)


def fatal_error(text):
    raise RuntimeError(text)


def log_debug(*args, **kwargs):
    log.debug(*args, **kwargs)


def log_info(*args, **kwargs):
    log.info(*args, **kwargs)


def log_error(*args, **kwargs):
    log.error(*args, **kwargs)


def log_warning(*args, **kwargs):
    log.warning(*args, **kwargs)


def log_fatal(*args, **kwargs):
    log.fatal(*args, **kwargs)
