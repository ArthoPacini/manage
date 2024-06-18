#!/usr/bin/env python3
import sys
import subprocess
import os
import logging
from argparse import ArgumentParser

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def decrypt_env(env_file):
    try:
        with subprocess.Popen(['gpg', '--decrypt', env_file], 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.PIPE, 
                              text=True) as proc:
            stdout, stderr = proc.communicate()

            if proc.returncode == 0:
                logging.info("Decryption successful")
                env_vars = {}
                for line in stdout.strip().split('\n'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key] = value
                return env_vars
            else:
                logging.error(f"Decryption failed: {stderr}")
                return None
    except Exception as e:
        logging.error(f"An error occurred while decrypting: {e}")
        return None


def load_environment(env_name):
    env_path = f"./.env/.env.{env_name}"
    if os.path.exists(f"{env_path}.gpg"):
        return decrypt_env(f"{env_path}.gpg")
    elif os.path.exists(env_path):
        with open(env_path) as f:
            return {line.split('=')[0]: line.split('=')[1].strip() for line in f if line.strip() and not line.startswith('#')}
    else:
        logging.error(f"Environment file {env_name} not found.")
        sys.exit(1)

def load_compose_file(env_name):
    """
    Load the Docker Compose file based on the environment.
    Tries to load docker-compose.{env_name}.yaml first, then falls back to docker-compose.yaml.
    """
    filenames = [f"docker-compose.{env_name}.yaml", "docker-compose.yaml"]
    for filename in filenames:
        try:
            with open(filename, 'r') as file:
                logging.info(f"Loaded configuration from {filename}")
                return file.read()
        except FileNotFoundError:
            logging.debug(f"{filename} not found.")

    logging.error("No suitable docker-compose file found.")
    sys.exit(1)

def modify_compose_file(compose_content, env_vars):
    """
    Replace placeholders in the compose file content with values from environment variables.
    """
    for key, value in env_vars.items():
        compose_content = compose_content.replace('${{{}}}'.format(key), value)
    return compose_content

def run_compose(tool, command, service, project_name, env_name, env_vars):
    compose_content = load_compose_file(env_name)
    compose_content = modify_compose_file(compose_content, env_vars)

    if "docker" in tool:
        compose_command = ["docker-compose", "-p", project_name, "-f", "-", command]
    else:
        compose_command = ["podman-compose", "-p", project_name, "-f", "-", command]

    if command == "up":
        compose_command.append("-d")
    if service != "all":
        compose_command.append(service)

    logging.info(f"Running command: {' '.join(compose_command)}")
    subprocess.run(compose_command, input=compose_content, text=True)


def main():
    parser = ArgumentParser(description="Manage Docker or Podman containers.")
    parser.add_argument("action", nargs='?', choices=['up', 'down', 'restart', 'build', 'pause'], help="Container action")
    parser.add_argument("service", nargs='?', default="all", help="Specify the service or 'all'")
    parser.add_argument("env_name", nargs='?', default="development", help="Environment name, defaults to 'development'")
    parser.add_argument("tool", nargs='?', default="podman", choices=['podman', 'docker'], help="Tool to use for managing containers")
    args = parser.parse_args()

    # Set the default project name after parsing the arguments
    default_project_name = os.path.basename(os.getcwd()) + f"_{args.env_name}"
    parser.add_argument("-p", "--project-name", default=default_project_name, help="Project name, defaults to the current directory name followed by '_{environment}'")
    args = parser.parse_args()

    if None in [args.action, args.service, args.env_name, args.tool]:
        parser.print_help()
        sys.exit(1)

    env_vars = load_environment(args.env_name)
    if env_vars is None:
        logging.error("Failed to load environment variables. Exiting.")
        sys.exit(1)

    run_compose(args.tool, args.action, args.service, args.project_name, args.env_name, env_vars)

if __name__ == '__main__':
    main()
