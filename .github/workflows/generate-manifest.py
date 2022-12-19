#!/usr/bin/env python3
import argparse
import yaml
import pathlib 
import subprocess

def generate_manifest(src_image, dst_image):
    return {
            "image": f"{dst_image}",
            "manifests": [
                {
                    "image": f"{src_image}_aarch64",
                    "platform": {
                        "architecture": "arm64",
                        "os": "linux",
                        "variant": "v8"
                    }
                },
                {
                    "image": f"{src_image}_x86_64",
                    "platform": {
                        "architecture": "amd64",
                        "os": "linux"
                    }
                }
            ]
    }


parser = argparse.ArgumentParser(prog = 'generate-manifest', description = 'generate a manifest')

parser.add_argument('--build_yaml')

parser.add_argument('--image')
parser.add_argument('--tag')
parser.add_argument('--src_tag')
parser.add_argument('--repo')
parser.add_argument('--docker_prefix')

args = parser.parse_args()

#print("hello")
#print(args.build_yaml)
fcontent = pathlib.Path(args.build_yaml).read_text()
#print(fcontent)
build = yaml.full_load(fcontent)
#print(build)
for name, val in build['services'].items():
    src_image = subprocess.run(['bash', '-c', f"echo -n {val['image']}"], stdout=subprocess.PIPE).stdout.decode('utf-8')
    src_images=[]
    #print(f"# {res}")
    dst_image = f"{':'.join(src_image.split(':')[:-1])}:{args.tag}"
    for arch in ["x86_64", "aarch64"]:
        src_images.append("--amend")
        src_images.append(f"{src_image}_{arch}")
    print(f"docker manifest create {dst_image} {' '.join(src_images)}")
    print(f"docker manifest push {dst_image}")


    #${DOCKER_ORG:-mailu}/${DOCKER_PREFIX:-}setup:${PINNED_MAILU_ARCH_VERSION:-local}
    #       "PINNED_MAILU_ARCH_VERSION": args.src_tag,
    #       "DOCKER_ORG": args.repo,
    #       "DOCKER_PREFIX": args.docker_prefix,
    #print(val['image'])
    #print(yaml.dump(generate_manifest(dst_image=dst_image, src_image=res)))
    #bash -c "echo \"${DOCKER_ORG:-mailu}/${DOCKER_PREFIX:-}nginx:${PINNED_MAILU_ARCH_VERSION:-local}\""
#mailu/nginx:local
#


