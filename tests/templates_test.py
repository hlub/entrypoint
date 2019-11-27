"""Test jinja2 template rendering and its configuration."""

import io
from unittest.mock import patch, Mock, call
from pytest import raises
import jinja2.exceptions

from entrypoint.templates import *

@patch('os.stat')
@patch('shutil.chown', autospec=True)
@patch('shutil.copymode')
def test_copymode(mock_copymode, mock_chown, mock_stat):
    """Should copy user, group and mode."""
    mock_stat.return_value = os.stat('/')
    copymode('src', 'dst')
    mock_stat.assert_called_with('src')
    mock_chown.assert_called_once()
    assert 'dst' == mock_chown.call_args[0][0]
    mock_copymode.assert_called_once_with('src', 'dst')


@patch('os.path.exists')
@patch('os.mkdir')
@patch('entrypoint.templates.copymode')
def test_make_output_dirs(copymode, mkdir, exists):
    """Function make_output_dirs() should create missing output directories
    and copy the corresponding ownership and mode.
    """
    exists.return_value = False
    make_output_dirs('/etc/nginx', '/templates/etc/nginx')
    assert mkdir.call_args_list == [
        call('/etc'),
        call('/etc/nginx')
    ]
    assert copymode.call_args_list == [
        call('/templates/etc', '/etc'),
        call('/templates/etc/nginx', '/etc/nginx')
    ]
    mkdir.reset_mock()
    copymode.reset_mock()

    exists.side_effect = lambda p: len(p) <= len('/etc')
    make_output_dirs('/etc/nginx/conf.d', '/templates/etc/nginx/conf.d')
    assert mkdir.call_args_list == [
        call('/etc/nginx'),
        call('/etc/nginx/conf.d')
    ]
    assert copymode.call_args_list == [
        call('/templates/etc/nginx', '/etc/nginx'),
        call('/templates/etc/nginx/conf.d', '/etc/nginx/conf.d')
    ]


def test_render_string():
    """Should render a given template with the specified variables."""
    assert render_string('some text', {}) == 'some text'
    assert render_string('{{ var }}', {'var': 'hello'}) == 'hello'


def test_jinja_do_extension_enabled():
    """Jinja2's extension for 'do' keyword should be enabled."""
    out = render_string('{%- do some_dict.update({"var": 1}) -%}'
                        '{{ some_dict.var }}',
                        {'some_dict': {}})
    assert out == '1'


def test_raise_error_on_undefined_variable():
    """Be strict about undefined variables, should raise an error."""
    with raises(jinja2.exceptions.UndefinedError):
        render_string('{{ not_found }}', {})


def test_process_templates_jinja_root_within_template_root():
    """When calling proces_templates(), the jinja_root should never be
    inside template_root.
    """
    with raises(AssertionError):
        process_templates({},
                          output_root='',
                          template_root='/templates',
                          jinja_root='/templates/jinja')


@patch('entrypoint.templates.copymode')
@patch('builtins.open')
@patch('os.mkdir')
@patch('os.path.exists')
@patch('os.stat')
@patch('os.walk')
def test_process_templates(walk, stat, exists, mkdir, open, copymode):
    outputs = {}

    def open_call(filename, mode):
        if 'r' in mode:
            assert filename.startswith('/templates')
            # file contains template filenae
            return io.BytesIO(filename.encode())
        # empty file
        file = io.StringIO()
        file.close = Mock() # it should not be closed before inspecting :(
        outputs[filename] = file
        return file

    def copymode_call(src, dst):
        assert src.startswith('/templates')
        relpath = os.path.relpath(src, '/templates')
        assert dst == '/' + relpath

    open.side_effect = open_call
    copymode.side_effect = copymode_call
    walk.return_value = [
        ['/templates', [], ['template1']],
        ['/templates/etc', [], ['template2']],
    ]
    exists.side_effect = lambda p: True if p.startswith('/templates') else False
    stat.return_value = os.stat('/')

    process_templates({},
                      output_root='/',
                      template_root='/templates',
                      jinja_root='/jinja')

    # missing output directory should be created
    mkdir.assert_called_with('/etc')

    # check output
    for filename, file in outputs.items():
        assert file.close.called
        assert file.getvalue().strip().endswith(filename)


@patch('entrypoint.templates.copymode')
@patch('builtins.open')
@patch('os.path.exists')
@patch('os.walk')
def test_process_templates_skips_already_existing(walk, exists, open, copymode):
    """Already existing output files should not be overridden."""
    walk.return_value = [
        ['/templates', [], ['template1']],
        ['/templates/etc', [], ['template2']],
    ]
    exists.return_value = True

    process_templates({},
                      output_root='/',
                      template_root='/templates',
                      jinja_root='/jinja')

    assert not open.called
    assert not copymode.called
