"""Process jinja2 templates"""

import os
import shutil
import logging
from jinja2 import BaseLoader, Environment, FileSystemLoader, StrictUndefined
from . import jinja_globals
from . import jinja_filters

log = logging.getLogger(__name__)

class SourceLoader(BaseLoader):
    """Template loader that does not really load but uses the given
    string as a template.
    """

    def get_source(self, environment, template):
        """Passes the given template string as the actual template.
        The returned values are: (template, filename, realod function).
        """
        return template, None, lambda: True


def load_jinja_filters():
    """A generator that loads jinja filters from the jinja_filters 
    module."""
    for name, filter_func in jinja_filters.__dict__.items():
        if name.startswith('_'):
            continue
        if not callable(filter_func):
            continue
        yield name, filter_func

def load_jinja_globals():
    """A generator that loads jinja globals from the jinja_globals 
    module.
    """
    module_type = type(__builtins__)
    for name, value in jinja_globals.__dict__.items():
        if name.startswith('_'):
            continue
        # take extra caution to exclude modules and packages
        if isinstance(value, module_type):
            continue
        yield name, value

def get_env(loader):
    """Returns a Jinja2 environment with required configuration and the
    additional globals and filters.
    """
    env = Environment(loader=loader,
                      keep_trailing_newline=True,
                      undefined=StrictUndefined,
                      extensions=['jinja2.ext.do'])
    for name, func in load_jinja_globals():
        env.globals[name] = func
    for name, jinja_filter in load_jinja_filters():
        env.filters[name] = jinja_filter
    return env


def copymode(src, dst):
    """Copy file permissions, user and group from `src` to `dst`."""
    src_stat = os.stat(src)

    shutil.chown(dst, user=src_stat.st_uid, group=src_stat.st_gid)
    shutil.copymode(src, dst)


def make_output_dirs(output_path, input_path):
    """Create all missing output directories and copy ownership and mode from
    the input_path. The output and input paths must have a common suffix.
    """
    dirs = []
    while not os.path.exists(output_path):
        dir_pair = (output_path, input_path)
        output_path, out_name = os.path.split(output_path)
        input_path, in_name = os.path.split(input_path)
        if out_name != in_name:
            break # the common part is over
        dirs.append(dir_pair)
    for output_path, input_path in reversed(dirs):
        os.mkdir(output_path)
        copymode(input_path, output_path)



def render_string(string, variables):
    """Render the given string with the specified variables."""
    env = get_env(SourceLoader())
    return env.get_template(string).render(variables)


def process_templates(variables, output_root, template_root, jinja_root=None):
    """Process files recursively under `template_root` as Jinja2 templates
    and store the results under `output_root` with the original relative
    directory structure. Missing directories are automatically created with
    their ownership and mode copied. Additional Jinja2 helper macros can be
    loaded from `jinja_root`.
    """
    log.debug('Processing templates from {!r}.'.format(template_root))
    template_roots = [template_root]
    if jinja_root:
        log.debug('Templates can be included from {!r}'.format(jinja_root))
        # assert that jinja_root is outside of the template_root
        assert os.path.relpath(jinja_root, template_root).startswith('..')
        template_roots.append(jinja_root)

    env = get_env(FileSystemLoader(template_roots))
    for template_dir, dirs, files in os.walk(template_root):
        relative_dir = os.path.relpath(template_dir, template_root)
        output_dir = os.path.join(output_root, relative_dir)

        make_output_dirs(output_dir, template_dir)

        for file in files:
            template_file = os.path.join(template_dir, file)
            output_file = os.path.abspath(os.path.join(output_dir, file))
            if os.path.exists(output_file):
                log.warning('File {!r} has a template defined but already exists, not overriding'.format(output_file))
                continue
            log.debug('Processing template {!r}'.format(template_file))
            template = env.get_template(os.path.join(relative_dir, file))
            output = template.render(variables)
            with open(output_file, 'w') as out:
                out.write(output)
            copymode(template_file, output_file)
