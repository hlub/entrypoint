"""Initialization hooks"""

import os
import glob
import logging

log = logging.getLogger(__name__)

class Hooks(object):
    """Loader and executor of the entrypoint hooks."""

    def __init__(self, options):
        self._modules = []
        try:
            hook_path_pattern = os.path.join(options.hooks_root, '*.py')
            module_paths = sorted(glob.glob(hook_path_pattern))
            log.debug('Found %d init hooks with pattern %r.',
                      len(module_paths), hook_path_pattern)
            for module_path in module_paths:
                module_name, _ = os.path.splitext(os.path.basename(module_path))
                log.debug('Loading init hooks %r from %r', module_name, module_path)
                module = self.import_file('entrypoint_hook_{}'.format(module_name), module_path)
                # Give an error if there is nothing to call:
                if not any(map(lambda x: hasattr(module, x), ['prehook', 'hook', 'posthook'])):
                    raise RuntimeError('Startup script {!r} does not contain any of the hook'
                                       'functions (prehoo, hook, posthook)!'.format(module_path))
                self._modules.append(module)
        except OSError:
            pass
    def import_file(self, full_name, path):
        """Import a python module from a path. Python 3.4+ only."""
        from importlib import util
        spec = util.spec_from_file_location(full_name, path)
        mod = util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            log.critical('Error while loading init hooks {!r} from {!r}!'.format(full_name, path))
            raise e
        return mod
    def run_prehooks(self, variables):
        """Run all pre-hooks."""
        for module in self._modules:
            if hasattr(module, 'prehook'):
                module.prehook(variables)
    def run_posthooks(self, variables):
        """Run all hooks and post-hooks."""
        for module in self._modules:
            if hasattr(module, 'hook'):
                module.hook(variables)
        for mod in self._modules:
            if hasattr(mod, 'posthook'):
                mod.posthook(vars)
