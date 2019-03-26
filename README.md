## docker-job

[![Build Status](https://travis-ci.org/starlingtrust/docker-job.svg)](https://travis-ci.org/starlingtrust/docker-job)

**docker-job** is a wrapper that allows [Docker]() containers to be manipulated as command-line utilities, as if the program in this container was a local executable.

Although `docker run` and `docker exec` are available options to run containers in a terminal, **docker-job** performs two key tasks:

1. It properly handles *standard input*, *standard output* and *standard error* streams. This makes it possible to redirect the container's output to files, and/or to pipe data in:

   ```bash
   $ cat my_input | docker-job \
       my_container:latest \
       1> my_output.txt \
       2> my_errors.txt
   ```
   Exit code are also properly handled; **docker-job** will exit with the same exit code as the program you ran in the container.

2. It automatically maps *input* and *output files* provided on the command line to paths that are mounted into the container, thus giving the container's program direct access to these files. This is done simply by adding a prefix `input:` or `output:` to files and folders you pass on the command line:

   ```bash
   $ ls
   my_input.txt
   $ docker-job ajmazurie/probe:latest -- \
      cat input:my_input.txt -o output:my_output.txt
   $ ls
   my_input.txt  my_output.txt
   ```

### Installation

**docker-job** is a [Python]() script, with only one dependency: the official Python [client]() for Docker.

### Quickstart

**docker-job** has a simple syntax: `docker-job <1> [-- <2>]`, with `<1>` being the name of a Docker image plus some options about the Docker server to use, and `<2>` the command line arguments to run within the container. Some examples:

- Create a report about the default Docker environment:
  `$ docker-job ajmazurie/probe:latest -- --to-file output:report.json`

### Notes

- **docker-job** was designed to run Docker containers to completion; however, nothing prevents it to be used for always-on ('detached') containers, such as web or database servers. Killing the **docker-job** process will automatically kill the corresponding container.

- **docker-job** applies simple rules when mapping inputs and output files to paths inside the container:
  - A file or folder tagged as input must exist on the host, and be readable by the current user; an error will be thrown if any or both of these conditions are not met.
  - The path to a file or folder tagged as output must exist on the host; if it doesn't, it will be automatically created with each intermediary folder set to permission `700` (or `u=rwx,go=`). If it exists already, it must be writable by the current user.
  - A file or folder tagged as both input and output must satisfy the two previous sets of constraints.
