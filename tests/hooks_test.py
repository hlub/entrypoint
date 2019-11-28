"""Tests for entrypoint hooks."""

from os import path
from unittest.mock import patch, Mock
from pytest import fixture, raises, mark
from entrypoint.hooks import Hooks


@patch("glob.glob")
@patch.object(Hooks, "import_file")
def test_hooks_init(import_file, glob):
    """Hooks use glob to collect entrypoint hook modules and honours the 
    specified root directory.
    """
    root_dir = "/root_dir_for_hooks"
    hook_file = path.join(root_dir, "hook.py")
    glob.return_value = [hook_file]
    Hooks(root_dir)
    assert glob.call_args[0][0].startswith(root_dir + "/")
    import_file.assert_called_once()
    assert import_file.call_args[0][1] == hook_file


def test_run_prehooks():
    """Should run prehook() functions from those modules that contain such
    function.
    """
    hooks = Hooks("/nonexisting")
    module1 = Mock(spec=["prehook"])
    module2 = Mock(spec=["hook"])
    hooks._modules = [module1, module2]
    hooks.run_prehooks({})
    module1.prehook.assert_called_once_with({})
    module2.hook.assert_not_called()


def test_run_posthooks():
    """Should run hook() and posthook() functions from those modules that
    contain such function.
    """
    hooks = Hooks("/nonexisting")
    module1 = Mock(spec=["prehook"])
    module2 = Mock(spec=["hook"])
    module3 = Mock(spec=["posthook"])
    hooks._modules = [module1, module2, module3]
    hooks.run_posthooks({})
    module1.prehook.assert_not_called()
    module2.hook.assert_called_once_with({})
    module3.posthook.assert_called_once_with({})


@patch("glob.glob")
@patch.object(Hooks, "import_file")
def test_hook_module_impor_raises(import_file, glob):
    """When import raises an error, it is time to halt."""
    glob.return_value = ["path"]
    import_file.side_effect = SyntaxError()
    with raises(SyntaxError):
        hooks = Hooks("/nonexisting")


@patch("glob.glob")
@patch.object(Hooks, "import_file")
def test_module_without_hooks(import_file, glob):
    """When no hook functions found, just skip that module."""
    glob.return_value = ["path"]
    import_file.return_value = Mock(spec=[])  # no hooks, hasattr -> False
    hooks = Hooks("/nonexisting")
    assert not hooks._modules, "no hooks should be listend"
