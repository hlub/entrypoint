"""Jinja filter additions.."""

import json
import random
from unittest.mock import patch
from pytest import mark, raises

from entrypoint.jinja_filters import *
from entrypoint.templates import render_string

def test_split():
    """Should split a string"""
    string = 'a,b,c'
    out = render_string('{{ string | split }}', {'string': string})
    assert out == repr(string.split())
    out = render_string('''{{ string | split(',') }}''', {'string': string})
    assert out == repr(string.split(','))
    out = render_string('''{{ string | split(',', maxsplit=2) }}''', {'string': string})
    assert out == repr(string.split(',', maxsplit=2))


def test_to_json():
    """Should produce JSON string."""
    out = render_string('{{ var | to_json }}', {'var': {'a':[0,1], 'b':None}})
    assert out == '''{"a": [0, 1], "b": null}'''


def test_to_pretty_json():
    """Should produce a more pretty JSON string."""
    var = {'a':[0,1], 'b':None}
    out = render_string('{{ var | to_pretty_json }}', {'var': var})
    assert out == json.dumps(var, indent=4, sort_keys=True)


def test_unique():
    """Should ensure that the output values are unique."""
    for _ in range(10):
        values = random.choices('0123456789', k=10)
        out = render_string('{{ values | unique | sort }}', {'values': values})
        assert out == repr(list(sorted(set(values))))
    out = render_string('{{ values | unique | sort }}', {'values': [{'x':1}, {'x':1}]})
    assert out == '''[{'x': 1}]'''


def test_union():
    """Should perform union between the value and the argument."""
    out = render_string('{{ set1 | union(set2) }}', {'set1': {1,2,3}, 'set2': set()})
    assert out == '{1, 2, 3}'
    out = render_string('{{ set1 | union(set2) }}', {'set1': {1,2,3,4}, 'set2': {2,3}})
    assert out == '{1, 2, 3, 4}'
    out = render_string('{{ set1 | union(set2) }}', {'set1': [{'x':0}], 'set2': [{'x':1}]})
    assert out == '''[{'x': 0}, {'x': 1}]'''
    out = render_string('{{ set1 | union(set2) }}', {'set1': [1,2,3,4], 'set2': [2,3]})
    assert out == '{1, 2, 3, 4}'


def test_intersect():
    """Should perform intersection between the value and the argument."""
    out = render_string('{{ set1 | intersect(set2) }}', {'set1': {1,2,3,4}, 'set2': set()})
    assert out == 'set()'
    out = render_string('{{ set1 | intersect(set2) }}', {'set1': {1,2,3,4}, 'set2': {2,3}})
    assert out == '{2, 3}'
    out = render_string('{{ set1 | intersect(set2) }}', {'set1': [[0,1],[1,2]], 'set2': [[2,3],[1,2]]})
    assert out == '[[1, 2]]'


def test_difference():
    """Should perform set difference between the value and the other iterables."""
    out = render_string('{{ set1 | difference(set2) }}', {'set1': {1,2,3,4}, 'set2': {4,5}})
    assert out == '{1, 2, 3}'


def test_symmetric_difference():
    """Should perform synnetric difference."""
    out = render_string('{{ set1 | symmetric_difference(set2) }}', {'set1': {1,2,3,4}, 'set2': {4,5}})
    assert out == '{1, 2, 3, 5}'
    out = render_string('{{ set2 | symmetric_difference(set1) }}', {'set1': {1,2,3,4}, 'set2': {4,5}})
    assert out == '{1, 2, 3, 5}'
