"""Additional Jinja template filters

Define all custom filters for Jinja templates within the scope of this 
module. Remember to prefix internal helper functions with undescore.
Only functions are collected as filters.
"""

import json

def split(value, sep=None, maxsplit=-1):
    return value.split(sep, maxsplit)


def to_json(value, *args, **kwargs):
    """Translates value into JSON."""
    return json.dumps(value, *args, **kwargs)


def to_pretty_json(value, *args, **kwargs):
    """Translates value into more pretty JSON."""
    return json.dumps(value, indent=4, sort_keys=True, *args, **kwargs)


def unique(value):
    """ENsure that al values are unique."""
    try:
        result = set(value)
    except TypeError:
        result = []
        for x in value:
            if x not in result:
                result.append(x)
    return result


def union(value, other):
    """Performs union between the filtered value and the argument."""
    try:
        result = set(value).union(set(other))
    except TypeError:
        result = []
        for item in value:
            result.append(item)
        for item in other:
            result.append(item)
        result = unique(result)
    return result


def intersect(value, other):
    """Performs intersection between the filtered value and the argument."""
    try:
        result = set(value).intersection(set(other))
    except TypeError:
        result = unique(list(filter(lambda x: x in other, value)))
    return result

def difference(value, other):
    """Return the difference of the value and the other set
    (i.e. all elements that are in the value set but not the other).
    """
    try:
        result = set(value) - set(other)
    except TypeError:
        result = unique(filter(lambda x: x not in other, value))
    return result

def symmetric_difference(value, other):
    """Return the symmetric difference of two sets, value and other.
    (i.e. all elements that are in exactly one of the sets.)
    """
    try:
        result = set(value).symmetric_difference(set(other))
    except TypeError:
        result = unique(filter(lambda x: x not in intersect(value, other),
                union(value, other)))
    return result
