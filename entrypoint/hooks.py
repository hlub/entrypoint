"""Initialization hooks"""

import os
import glob
import logging
from importlib import util


log = logging.getLogger(__name__)


class Hooks(object):
    """Loader and executor of the entrypoint hooks."""

    def __init__(self, hooks_root):
        """Load hook modules under the `hooks_root` directory."""
        self._modules = []
        hook_path_pattern = os.path.join(hooks_root, "*.py")
        module_paths = sorted(glob.glob(hook_path_pattern))
        log.debug(
            "Found %d init hooks with pattern %r.",
            len(module_paths),
            hook_path_pattern,
        )
        for module_path in module_paths:
            module_name, _ = os.path.splitext(os.path.basename(module_path))
            log.debug("Loading init hooks %r from %r", module_name, module_path)
            module = self.import_file(
                "entrypoint_hook_{}".format(module_name), module_path
            )
            # Give an error if there is nothing to call:
            if self._has_hooks(module):
                self._modules.append(module)

    @staticmethod
    def _has_hooks(module):
        """Returns true if the module defines any of `prehook`, `hook`
        and `posthook`.
        """
        return any(map(lambda x: hasattr(module, x), ["prehook", "hook", "posthook"]))

    def import_file(self, full_name, path):
        """Import a python module from a path. Python 3.4+ only."""
        spec = util.spec_from_file_location(full_name, path)
        mod = util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as exc:
            log.critical("Error while loading init hooks %r from %r!", full_name, path)
            raise exc
        return mod

    def run_prehooks(self, variables):
        """Run all pre-hooks."""
        for module in self._modules:
            if hasattr(module, "prehook"):
                module.prehook(variables)

    def run_posthooks(self, variables):
        """Run all hooks and post-hooks."""
        for module in self._modules:
            if hasattr(module, "hook"):
                module.hook(variables)
        for mod in self._modules:
            if hasattr(mod, "posthook"):
                mod.posthook(variables)
