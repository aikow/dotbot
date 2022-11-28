import glob
import os
import subprocess
import sys
from argparse import ArgumentParser, RawTextHelpFormatter

import dotbot

from .config import ConfigReader, ReadingError
from .dispatcher import Dispatcher, DispatchError
from .messenger import Level, Messenger
from .util import module


CONFIG_FILENAME = "dotbot.json"


def add_options(parser):
    parser.add_argument(
        "-Q", "--super-quiet", action="store_true", help="suppress almost all output"
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="suppress most output"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="enable verbose output\n"
        "-v: typical verbose\n"
        "-vv: also, set shell commands stderr/stdout to true",
    )

    parser.add_argument(
        "-b",
        "--base-directory",
        help="execute commands from within BASEDIR",
        metavar="BASEDIR",
    )
    parser.add_argument(
        "-f",
        "--config-file",
        help="run commands given in CONFIGFILE",
        metavar="CONFIG",
    )
    parser.add_argument(
        "-d",
        "--config-dir",
        help="Run all configs that are in the config dir.",
        metavar="CONFIGS",
    )

    parser.add_argument(
        "-p",
        "--plugin",
        action="append",
        dest="plugins",
        default=[],
        help="load PLUGIN as a plugin",
        metavar="PLUGIN",
    )
    parser.add_argument(
        "--disable-built-in-plugins",
        action="store_true",
        help="disable built-in plugins",
    )
    parser.add_argument(
        "--plugin-dir",
        action="append",
        dest="plugin_dirs",
        default=[],
        metavar="PLUGIN_DIR",
        help="load all plugins in PLUGIN_DIR",
    )

    parser.add_argument(
        "-o",
        "--only",
        nargs="+",
        help="only run specified directives",
        metavar="DIRECTIVE",
    )
    parser.add_argument(
        "-e",
        "--except",
        nargs="+",
        dest="skip",
        help="skip specified directives",
        metavar="DIRECTIVE",
    )

    parser.add_argument(
        "--force-color",
        dest="force_color",
        action="store_true",
        help="force color output",
    )
    parser.add_argument(
        "--no-color", dest="no_color", action="store_true", help="disable color output"
    )

    parser.add_argument(
        "--version", action="store_true", help="show program's version number and exit"
    )

    parser.add_argument(
        "-x",
        "--exit-on-failure",
        dest="exit_on_failure",
        action="store_true",
        help="exit after first failed directive",
    )


def read_config(config_file):
    reader = ConfigReader(config_file)
    return reader.get_config()


def main():
    log = Messenger()
    try:
        parser = ArgumentParser(formatter_class=RawTextHelpFormatter)
        add_options(parser)
        options = parser.parse_args()

        if options.version:
            try:
                with open(os.devnull) as devnull:
                    git_hash = subprocess.check_output(
                        ["git", "rev-parse", "HEAD"],
                        cwd=os.path.dirname(os.path.abspath(__file__)),
                        stderr=devnull,
                    )
                hash_msg = " (git %s)" % git_hash[:10]
            except (OSError, subprocess.CalledProcessError):
                hash_msg = ""
            print("Dotbot version %s%s" % (dotbot.__version__, hash_msg))
            exit(0)

        if options.super_quiet:
            log.set_level(Level.WARNING)
        if options.quiet:
            log.set_level(Level.INFO)
        if options.verbose > 0:
            log.set_level(Level.DEBUG)

        if options.force_color and options.no_color:
            log.error("`--force-color` and `--no-color` cannot both be provided")
            exit(1)
        elif options.force_color:
            log.use_color(True)
        elif options.no_color:
            log.use_color(False)
        else:
            log.use_color(sys.stdout.isatty())

        # Load builtin plugins
        if not options.disable_built_in_plugins:
            from .plugins import Clean, Create, Link, Shell

        plugin_paths = []

        for directory in list(options.plugin_dirs):
            for plugin_path in glob.glob(os.path.join(directory, "*.py")):
                plugin_paths.append(plugin_path)

        for plugin_path in options.plugins:
            plugin_paths.append(plugin_path)

        for plugin_path in plugin_paths:
            abspath = os.path.abspath(plugin_path)
            module.load(abspath)

        configs = []
        if options.config_file:
            conf_file = os.path.abspath(options.config_file)
            conf_dir = os.path.dirname(conf_file)
            conf = os.path.basename(conf_dir)
            configs.append((conf, conf_dir, conf_file))

        if options.config_dir:
            for conf in os.listdir(options.config_dir):
                conf_dir = os.path.abspath(os.path.join(options.config_dir, conf))
                conf_file = os.path.join(conf_dir, CONFIG_FILENAME)
                if not os.path.isdir(conf_dir):
                    log.lowinfo("Skipped config '{}': Not a directory".format(conf))
                elif not os.path.isfile(conf_file):
                    log.lowinfo(
                        "Skipped config '{}': No configuration file found".format(conf)
                    )
                else:
                    configs.append((conf, conf_dir, conf_file))

        if not configs:
            log.error("No configuration files specified")
            exit(1)

        for conf, conf_dir, conf_file in configs:
            log.info("\nRunning config for '{}'".format(conf))
            log.lowinfo("Base directory: '{}'".format(conf_dir))
            log.lowinfo("Config file: '{}'".format(conf_file))

            tasks = read_config(conf_file)
            if tasks is None:
                log.warning("Configuration file is empty, no work to do")
                tasks = []

            if not isinstance(tasks, list):
                raise ReadingError("Configuration file must be a list of tasks")

            os.chdir(conf_dir)
            dispatcher = Dispatcher(
                conf_dir,
                only=options.only,
                skip=options.skip,
                exit_on_failure=options.exit_on_failure,
                options=options,
            )

            success = dispatcher.dispatch(tasks)
            if success:
                log.info("==> All tasks executed successfully")
            else:
                raise DispatchError("\n==> Some tasks were not executed successfully")

    except (ReadingError, DispatchError) as e:
        log.error("%s" % e)
        exit(1)
    except KeyboardInterrupt:
        log.error("\n==> Operation aborted")
        exit(1)
