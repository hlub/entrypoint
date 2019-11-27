Entrypoint for containers
=========================

**Entrypoint** offers extensible entrance and init functionality for containers such as [Docker][docker] and [Kubernetes][kubernetes].
It allows template-induced configuration, extensible initialization routines and works as a simple process supervisor and init system designed to run as PID 1 inside minimal container environments.
**Entrypoint** is written in python3 and tested extensively.

Key features:

* A simple process supervisor and init system taking care of zombies and signal propagation.
* Configurability via environment variables and a YAML configuration file.
* Jinja2 templates to carry out the actual configurations.
* Ability to extend the initialization with Python-based hooks before and after the configuration step.

## Init system strongly inspired by [dumb-init][dumb-init]

Lightweight containers have popularized the idea of running a single process or
service without normal init systems like [systemd][systemd] or
[sysvinit][sysvinit]. However, omitting an init system often leads to incorrect
handling of processes and signals, and can result in problems such as
containers which can't be gracefully stopped, or leaking containers which
should have been destroyed.

`entrypoint` enables you to simply prefix your command with `entrypoint`. It acts
as PID 1 and immediately spawns your command as a child process, taking care to
properly handle and forward signals as they are received. You can always omit
this functionality with `entrypoint --no-init --`, which skips all init system
responsibilities and uses [exec][exec] to run your actual command after other
initializations.


### Why you need an init system

Normally, when you launch a Docker container, the process you're executing
becomes PID 1, giving it the quirks and responsibilities that come with being
the init system for the container.

There are two common issues this presents:

1. In most cases, signals won't be handled properly.

   The Linux kernel applies special signal handling to processes which run as
   PID 1.

   When processes are sent a signal on a normal Linux system, the kernel will
   first check for any custom handlers the process has registered for that
   signal, and otherwise fall back to default behavior (for example, killing
   the process on `SIGTERM`).

   However, if the process receiving the signal is PID 1, it gets special
   treatment by the kernel; if it hasn't registered a handler for the signal,
   the kernel won't fall back to default behavior, and nothing happens. In
   other words, if your process doesn't explicitly handle these signals,
   sending it `SIGTERM` will have no effect at all.

   A common example is CI jobs that do `docker run my-container script`: sending
   `SIGTERM` to the `docker run` process will typically kill the `docker run` command,
   but leave the container running in the background.

2. Orphaned zombie processes aren't properly reaped.

   A process becomes a zombie when it exits, and remains a zombie until its
   parent calls some variation of the `wait()` system call on it. It remains in
   the process table as a "defunct" process. Typically, a parent process will
   call `wait()` immediately and avoid long-living zombies.

   If a parent exits before its child, the child is "orphaned", and is
   re-parented under PID 1. The init system is thus responsible for
   `wait()`-ing on orphaned zombie processes.

   Of course, most processes *won't* `wait()` on random processes that happen
   to become attached to them, so containers often end with dozens of zombies
   rooted at PID 1.


### What `init` does

Unless otherwise specified, `entrypoint` runs as PID 1, acting like a simple init system. It launches a
single process and then proxies all received signals to a session rooted at
that child process.

Since your actual process is no longer PID 1, when it receives signals from
`entrypoint`, the default signal handlers will be applied, and your process will
behave as you would expect. If your process dies, `entrypoint` will also die,
taking care to clean up any other processes that might still remain.


#### Session behavior

In its default mode, `entrypoint` establishes a
[session](http://man7.org/linux/man-pages/man2/setsid.2.html) rooted at the
child, and sends signals to the entire process group. This is useful if you
have a poorly-behaving child (such as a shell script) which won't normally
signal its children before dying.

This can actually be useful outside of Docker containers in regular process
supervisors like [daemontools][daemontools] or [supervisord][supervisord] for
supervising shell scripts. Normally, a signal like `SIGTERM` received by a
shell isn't forwarded to subprocesses; instead, only the shell process dies.
With `entrypoint`, you can just write shell scripts with `entrypoint` in the shebang:

    #!/usr/bin/entrypoint /bin/sh
    my-web-server &  # launch a process in the background
    my-other-server  # launch another process in the foreground

Ordinarily, a `SIGTERM` sent to the shell would kill the shell but leave those
processes running (both the background and foreground!).  With `entrypoint`, your
subprocesses will receive the same signals your shell does.

If you'd like for signals to only be sent to the direct child, you can run with
the `--no-setsid` argument when running `entrypoint`. In this mode, 
`entrypoint` is completely transparent; you can even string multiple 
together (like `entrypoint --no-setsid -- entrypoint --no-setsid echo 'oh, hi'`).


#### Signal rewriting

`Entrypoint` allows rewriting incoming signals before proxying them. This is
useful in cases where you have a Docker supervisor (like Mesos or Kubernetes)
which always sends a standard signal (e.g. SIGTERM). Some apps require a
different stop signal in order to do graceful cleanup.

For example, to rewrite the signal SIGTERM to SIGQUIT,
just add `--rewrite term:quit` on the command line.

To drop a signal entirely, you can rewrite it to the special name `none`.

Note: Rewrites are case-insensitive and they may include the `sig` prefix.


##### Signal rewriting special case

When running in setsid mode, it is not sufficient to forward
`SIGTSTP`/`SIGTTIN`/`SIGTTOU` in most cases, since if the process has not added
a custom signal handler for these signals, then the kernel will not apply
default signal handling behavior (which would be suspending the process) since
it is a member of an orphaned process group. For this reason, we set default
rewrites to `SIGSTOP` from those three signals. You can opt out of this
behavior by rewriting the signals back to their original values, if desired.

One caveat with this feature: for job control signals (`SIGTSTP`, `SIGTTIN`,
`SIGTTOU`), `entrypoint` will always suspend itself after receiving the signal,
even if you rewrite it to something else.


## Initialization and configuration

`Entrypoint` offers 
Often containers want to do some pre-start work which can't be done during
build time. For example, you might want to template out some config files based
on environment variables or a more complex configuration. You may also want to
run some initial scripts to, for instance, setup a database.


### Templates

By defult `entrypoint` searches recursively for Jinja templates from 
the `/templates` directory. Each found file `/templates/<path>` is rendered 
with the environment and configuration variables, and the resulting document
placed in `/<path>`. If the destination file already exists, rendering of 
the corresponding template is skipped. So, make sure to delete those files
you will template on init. In this way, it is easy to override configuration
files from outside of the containers.

All non-existing sub-directories are copied form `/templates` including
ownership and mode. The template files also define the ownership and mode
of the resulting files.

Additional Jinja templates that do not represent a real file itself but will
be included from other templates can be plcaed under `/jinja` directory
(change the default location with `--jinja`).

Any rendering error causes `entrypoint` to print an error and stop. All Jinja
variables must be defined, but of course the `default` filter is useful for
allowing default values.


### YAML configuration

In some cases environment variables are enough to perform sibmple container
setups. However, if more complex configuration is needed, the configuartion
can be placed in a YAML configuration, which is then mapped to path
`/variables.yml` within the container (change the default path 
with `--variables`).

YAML configuration makes it possible to offer a simple configuration
of containers possibly configuring multiple services (such as barman and cron).
This encapsulates all configurations most probably of differen forms to
offer a signle containerized service.


### Hooks

Hooks are located in Python modules under `/entrypoint_hooks` directory 
(change with `--hooks`). Such module should define at least one of functions
`prehook(variables)`, `hook(variables)` or `posthook(variables)`. Prehooks
are executed before template rendering and can therefore even edit the
configuration variables. Hooks and posthooks are run after template redering.
The only variable for these functions is a dict-like variable space.


## Installing inside Docker containers

ToDo.


## Usage

Once installed inside your container, simply prefix your commands with
`entrypoint` (and make sure that you're using [the recommended JSON
syntax][docker-cmd-json]).

Within a Dockerfile, it's a good practice to use `entrypoint` as your container's
entrypoint. An "entrypoint" is a partial command that gets prepended to your
`CMD` instruction, making it a great fit for `entrypoint`:

```Dockerfile
# Runs "entrypoint -- /my/script --with --args"
# Note the double dash (--) which indicates that `entrypoint` stops handling
# its parameters and leaves the rest unprocessed.
ENTRYPOINT ["entrypoin", "--"]

# or if you use --rewrite or other cli flags
# ENTRYPOINT ["entrypoint", "--rewrite", "term:none", "--"]

CMD ["/my/script", "--with", "--args"]
```

If you declare an entrypoint in a base image, any images that descend from it
don't need to repeat it. They can just set a `CMD` as usual.

For interactive one-off usage, you can just prepend it manually:

    $ docker run my_container entrpoint -- python -c 'while True: pass'

Running this same command without `entrypoint` would result in being unable to
stop the container without `SIGKILL`, but with `entrypoint`, you can send it
more humane signals like `SIGTERM`.

It's important that you use [the JSON syntax][docker-cmd-json] for `CMD` and
`ENTRYPOINT`. Otherwise, Docker invokes a shell to run your command, resulting
in the shell as PID 1 instead of `entrypoint`.


## Development

To develop `entrypoint` further you can clone this repository, create a
virtualenv, install the requiremens and development requirements:

```bash
git clone https://github.com/hlub/entrypoint
cd entrypoint
virtualenv --python python3 venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Now you are ready to run the entrypoint with `python -m entrypoint.main`,
and you can run the tests with command `pytest`. 
    $ make
## See also

* [Docker and the PID 1 zombie reaping problem (Phusion Blog)](https://blog.phusion.nl/2015/01/20/docker-and-the-pid-1-zombie-reaping-problem/)
* [Trapping signals in Docker containers (@gchudnov)](https://medium.com/@gchudnov/trapping-signals-in-docker-containers-7a57fdda7d86)
* [Dump-init written in C](https://github.com/Yelp/dumb-init)


[daemontools]: http://cr.yp.to/daemontools.html
[docker-cmd-json]: https://docs.docker.com/engine/reference/builder/#run
[docker]: https://www.docker.com/
[exec]: https://en.wikipedia.org/wiki/Exec_(system_call)
[gh-releases]: https://github.com/hlub/entrypoint/releases
[supervisord]: http://supervisord.org/
[systemd]: https://wiki.freedesktop.org/www/Software/systemd/
[sysvinit]: https://wiki.archlinux.org/index.php/SysVinit
[dumb-init]: https://github.com/Yelp/dumb-init
