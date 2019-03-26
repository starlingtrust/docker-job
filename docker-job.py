#!/usr/bin/env python

import argparse
import uuid
import logging
import logging.config
import os
import sys

import docker
import docker.errors

__version__ = "0.1.3"

parser = argparse.ArgumentParser()

parser.add_argument("image",
    metavar="NAME[:TAG]",
    help="Name of the image")

parser.add_argument("--server-version",
    metavar="VERSION", default="auto",
    help="Docker server version (default: %(default)s)")

parser.add_argument("--remove-image",
    action="store_true", default=False,
    help="If set, remove the image after the run")

parser.add_argument("--keep-container",
    action="store_true", default=False,
    help="If set, keep the container after the run")

parser.add_argument("--debug",
    action="store_true", default=False,
    help="Display debugging information")

parser.add_argument("--version",
    action="version", version=__version__)

# separate docker-job arguments from the job arguments
if ("--" in sys.argv):
    i = sys.argv.index("--")
    args, job_args = sys.argv[:i], sys.argv[i+1:]
else:
    args, job_args = sys.argv, []

args = parser.parse_args(args[1:])

logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": True,
    "formatters": {"default": {
        "format": "%(asctime)s | %(name)s: %(levelname)s: %(message)s"}},
    "handlers": {"default": {
        "class": "logging.StreamHandler",
        "formatter": "default"}},
    "loggers": {"": {
        "handlers": ["default"],
        "level": logging.DEBUG if (args.debug) else logging.INFO,
        "propagate": True}}})

logger = logging.getLogger(
    os.path.splitext(os.path.basename(__file__))[0])

def error(msg, is_exception = False):
    if (is_exception) and (args.debug):
        logger.exception(msg)
    else:
        msg = str(msg).strip()
        logger.error(msg)
    sys.exit(1)

# extract paths from job arguments
job_args_, current_mode = [], None
for arg in job_args:
    if (arg.lower() in ("inputs:", "outputs:")):
        current_mode = arg.lower()[:-2]
        continue

    if (arg.lower() in (":inputs", ":outputs")):
        mode = arg.lower()[1:-1]
        if (current_mode != mode):
            error(("Invalid syntax: "
                "Cannot close '%ss:' block with ':%ss' tag" % (current_mode, mode)))
        current_mode = None
        continue

    if (current_mode is not None):
        arg = "%s:%s" % (current_mode, arg)

    job_args_.append(arg)

job_args = job_args_
del job_args_

def qualify_path(path: str):
    # check if this path exists, and if it is a folder
    exists = os.path.exists(path)
    if (exists):
        is_folder = os.path.isdir(path)
    else:
        # if the path doesn't exists, we consider
        # it to be a folder if it ends with a '/'
        is_folder = path.endswith(os.sep)

    # get an absolute, normalized path
    normalized_path = os.path.abspath(path)
    if (is_folder): normalized_path += os.sep

    return (normalized_path, exists, is_folder)

path_args, path_info = {}, {}
for (i, arg) in enumerate(job_args):
    mode = None
    if (arg.lower().startswith("input:")):
        arg, mode = arg[6:], "input"

    if (arg.lower().startswith("output:")):
        arg, mode = arg[7:], "output"

    if (mode is not None):
        (normalized_path, exists, is_folder) = qualify_path(arg)
        path_args.setdefault(normalized_path, []).append(i)
        if (not normalized_path in path_info):
            path_info[normalized_path] = (set(), exists, is_folder)
        path_info[normalized_path][0].add(mode)

# validate paths and generate binding pairs
def check_permissions(path: str, mode: int):
    if (not os.access(path, mode)):
        error("Invalid permissions: Cannot %s %s" % (
            {os.R_OK: "read", os.W_OK: "write"}[mode], path))

path_binds = {}
for (local_path, (mode, exists, is_folder)) in path_info.items():
    bind_target_prefix, path_arg = "/tmp/%s/" % uuid.uuid4().hex, None

    # if the path is an input,
    if ("input" in mode):
        # the path should exist on the host
        if (not exists):
            error("Not found: %s" % local_path)

        # the path should be readable on the host
        check_permissions(local_path, os.R_OK)

        # the bind target is the file name (or an
        # empty string if the path is a folder)
        bind_source = local_path
        bind_target = os.path.basename(local_path)

        path_arg = bind_target

    # if the path is an output,
    if ("output" in mode):
        # the parent of this path must exist on the host
        if (is_folder):
            parent_path = local_path
        else:
            parent_path = os.path.dirname(local_path) + os.sep

        if (not exists):
            os.makedirs(parent_path, mode=0o700, exist_ok=True)

        # the path should be writable on the host
        if (exists):
            check_permissions(local_path, os.W_OK)
        else:
            check_permissions(parent_path, os.W_OK)

        # the mount point is an empty string
        if (exists):
            bind_source = local_path
            bind_target = os.path.basename(local_path)
        else:
            bind_source = parent_path
            bind_target = ""

        path_arg = os.path.basename(local_path)

    for i in path_args[local_path]:
        job_args[i] = bind_target_prefix + path_arg

    path_binds[bind_source] = {
        "mode": "rw" if ("output" in mode) else "ro",
        "bind": bind_target_prefix + bind_target}

if (args.debug):
    # nicely display the volume binds
    lines = []
    for bind_source in sorted(path_binds):
        bind_source_ = os.path.relpath(bind_source, os.getcwd())
        if (bind_source.endswith(os.sep)):
            bind_source_ += os.sep
        lines.append("  '%s': %s" % (bind_source_, path_binds[bind_source]))
    if (len(lines) > 0):
        lines = "\n" + "\n".join(lines) + "\n "
    else:
        lines = ""
    logger.debug("path_binds={%s}", lines)

# build arguments for the Docker container
container_kwargs = {}

if (len(path_binds) > 0):
    container_kwargs["volumes"] = path_binds

container_kwargs["detach"] = True

try:
    client = docker.from_env(version=args.server_version)
    container = None

    try:
        image = client.images.get(args.image)

    except docker.errors.ImageNotFound:
        logger.debug("Pulling image '%s'", args.image)
        image = client.images.pull(args.image)

    try:
        logger.debug("container_kwargs=%s", container_kwargs)
        logger.debug("job_args=%s", job_args)

        container = client.containers.create(
            image, job_args, **container_kwargs)

        logger.debug("Running container %s", container.id)
        container.start()

        output = container.attach(
            stdout=True, stderr=True,
            stream=True, logs=True)

        for line in output:
            sys.stdout.write(line.decode("utf-8"))
            sys.stdout.flush()

        sys.exit(container.wait())

    except KeyboardInterrupt:
        if (container is not None):
            logger.debug("Killing container %s", container.id)
            container.kill()

    finally:
        if (container is not None) and (not args.keep_container):
            logger.debug("Removing container %s", container.id)
            container.remove(force=True)

        if (image is not None) and (args.remove_image):
            logger.debug("Removing image %s", image)
            client.images.remove(image)

except docker.errors.APIError as e:
    error(e, is_exception=True)
