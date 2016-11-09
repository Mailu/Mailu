from mailu import app

import docker
import signal


# Connect to the Docker socket
cli = docker.Client(base_url=app.config['DOCKER_SOCKET'])


def get(*names):
    result = {}
    all_containers = cli.containers(all=True)
    for brief in all_containers:
        if brief['Image'].startswith('mailu/'):
            container = cli.inspect_container(brief['Id'])
            container['Image'] = cli.inspect_image(container['Image'])
            name = container['Config']['Labels']['com.docker.compose.service']
            if not names or name in names:
                result[name] = container
    return result


def reload(*names):
    for name, container in get(*names).items():
        cli.kill(container["Id"], signal.SIGHUP.value)
