import sys
import os
import time
import datetime
from xmlrpc.client import DateTime
import docker
from colorama import Fore, Style
import subprocess
import calendar

# Declare variables for service name and sleep time
test_name=sys.argv[1]
timeout=int(sys.argv[2])
test_path="tests/compose/" + test_name + "/"
compose_file=test_path + "docker-compose.yml"

client = docker.APIClient(base_url='unix://var/run/docker.sock')

containers = []

# Stop containers
def stop(exit_code):
    print_logs()
    sys.stdout.flush()
    print(subprocess.check_output("docker-compose -f " + compose_file + " down", shell=True).decode())
    sys.exit(exit_code)

def health_checks(deadline):
    exit_code = 0
    #Iterating trough all containers dictionary
    for container in client.containers(all=True):
        #Perform "docker container inspect" on container based on container ID and save output to a dictionary
        container_inspect = client.inspect_container(container['Id']) #Dict

        if "Health" in container_inspect['State'].keys():
            if container_inspect['State']['Health']['Status'] == "healthy":
                print(Fore.GREEN + "Health status for " + container_inspect['Name'].replace("/", "") + " : " + Fore.CYAN + container_inspect['State']['Health']['Status'] + Style.RESET_ALL)
            if container_inspect['State']['Health']['Status'] != "healthy":
                print(Fore.RED + "Container " + container_inspect['Name'].replace("/", "") + " is " + Fore.YELLOW + container_inspect['State']['Health']['Status']
                      + Fore.RED + ", FailingStreak: " + Fore.YELLOW + str(container_inspect['State']['Health']['FailingStreak'])
                      + Fore.RED + ", Log: " + Fore.YELLOW + str(container_inspect['State']['Health']['Log']) + Style.RESET_ALL)
                exit_code = 1
        else:
            if container_inspect['State']['Status'] == "running":
                print(Fore.GREEN + "Running status for " + container_inspect['Name'].replace("/", "") + " : " + Fore.BLUE + container_inspect['State']['Status'] + Style.RESET_ALL)
            if container_inspect['State']['Status'] != "running":
                print(Fore.RED + "Container " + container_inspect['Name'].replace("/", "") + " state is: " + Fore.YELLOW + container_inspect['State']['Status'] + Style.RESET_ALL)
                exit_code = 1

        #Saving Id, Name and state to a new dictionary
        containers_dict = {}
        containers_dict['Name'] = container_inspect['Name'].replace("/", "")
        containers_dict['Id'] = container_inspect['Id']
        containers_dict['State'] = container_inspect['State']

        #Adding the generated dictionary to a list
        containers.append(containers_dict)

    if exit_code == 0:
        return True
    elif exit_code != 0 and deadline < datetime.datetime.now().timestamp():
        stop(exit_code)

def print_logs():
    print("Printing logs ...")
    #Iterating through docker container inspect list and print logs
    for container in containers:
        print(Fore.LIGHTMAGENTA_EX + "Printing logs for: " + Fore.GREEN + container['Name'] + Style.RESET_ALL)
        sys.stdout.flush()
        print(subprocess.check_output('docker container logs ' + container['Name'], shell=True).decode())

#Iterating over hooks in test folder and running them
def hooks():
    print(Fore.LIGHTMAGENTA_EX + "Running hooks" + Style.RESET_ALL)
    for test_file in sorted(os.listdir(test_path)):
        try:
            if test_file.endswith(".py"):
                sys.stdout.flush()
                print(subprocess.check_output("python3 " + test_path + test_file, shell=True).decode())
            elif test_file.endswith(".sh"):
                sys.stdout.flush()
                print(subprocess.check_output("./" + test_path + test_file, shell=True).decode())
        except subprocess.CalledProcessError as e:
            sys.stderr.write("[ERROR]: output = %s, error code = %s\n" % (e.output.decode(), e.returncode))
            stop(1)

# Start up containers
sys.stdout.flush()
deadline=datetime.datetime.now()+datetime.timedelta(minutes=timeout)
deadline=calendar.timegm(deadline.timetuple())
print(subprocess.check_output("docker-compose -f " + compose_file + " up -d", shell=True).decode())
print()
print(Fore.LIGHTMAGENTA_EX + "Sleeping for 10s" + Style.RESET_ALL)
time.sleep(10)
print()
sys.stdout.flush()
print(subprocess.check_output("docker ps -a", shell=True).decode())
print()
while not health_checks(deadline):
    print(Fore.LIGHTMAGENTA_EX + "Sleeping for 10s" + Style.RESET_ALL)
    sys.stdout.flush()
    time.sleep(10)
print()
hooks()
print()
stop(0)
