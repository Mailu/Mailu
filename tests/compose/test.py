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
setup_path=test_path + "setup"

client = docker.APIClient(base_url='unix://var/run/docker.sock')

containers = {}

def compose_container_ids():
    """Return only containers belonging to this compose test project."""
    result = subprocess.run(
        ["docker", "compose", "-f", compose_file, "ps", "--all", "-q"],
        check=True, capture_output=True, text=True,
    )
    return [container_id for container_id in result.stdout.splitlines() if container_id]

def report_container_state(container_id, name=None):
    """Print Docker's current state and recent health-check results."""
    try:
        details = client.inspect_container(container_id)
    except docker.errors.NotFound:
        print(f"  {name or container_id}: container no longer exists")
        return

    name = details.get("Name", "").lstrip("/") or name or container_id
    state = details.get("State", {})
    print(
        f"  {name} ({details.get('Id', container_id)[:12]}): "
        f"status={state.get('Status')}, running={state.get('Running')}, "
        f"exit_code={state.get('ExitCode')}, error={state.get('Error')!r}, "
        f"oom_killed={state.get('OOMKilled')}, restarting={state.get('Restarting')}, "
        f"started_at={state.get('StartedAt')}, finished_at={state.get('FinishedAt')}"
    )
    health = state.get("Health")
    if health is None:
        print("    health=not configured")
        return
    print(
        f"    health={health.get('Status')}, "
        f"failing_streak={health.get('FailingStreak')}"
    )
    for check in health.get("Log", [])[-5:]:
        output = (check.get("Output") or "").strip()
        if len(output) > 1000:
            output = output[-1000:]
        print(
            f"    check: exit_code={check.get('ExitCode')}, "
            f"started_at={check.get('Start')}, finished_at={check.get('End')}, "
            f"output={output!r}"
        )

def report_compose_health():
    print("Container health state at timeout:")
    for container_id in compose_container_ids():
        report_container_state(container_id)

# Stop containers
def stop(exit_code):
    print_logs()
    sys.stdout.flush()
    print(subprocess.check_output(f"docker compose -f {compose_file} down", shell=True).decode())
    sys.exit(exit_code)

def health_checks(deadline):
    exit_code = 0
    # Inspect only this compose project, not unrelated containers such as BuildKit.
    for container_id in compose_container_ids():
        container_inspect = client.inspect_container(container_id)

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
        containers[container_inspect['Id']] = {
            'Name': container_inspect['Name'].replace("/", ""),
            'Id': container_inspect['Id'],
        }

    if exit_code == 0:
        return True
    elif exit_code != 0 and deadline < datetime.datetime.now().timestamp():
        report_compose_health()
        stop(exit_code)

def wait_for_service_health(service, deadline):
    while True:
        container_id = subprocess.check_output(
            f"docker compose -f {compose_file} ps -q {service}", shell=True
        ).decode().strip()
        if container_id:
            details = client.inspect_container(container_id)
            containers[details['Id']] = {
                'Name': details['Name'].replace("/", ""),
                'Id': details['Id'],
            }
            state = details["State"]
            health = state.get("Health", {}).get("Status")
            if health == "healthy":
                print(Fore.GREEN + f"{service} is healthy" + Style.RESET_ALL)
                return
            if state.get("Status") not in ("created", "running"):
                print(Fore.RED + f"{service} stopped before becoming healthy" + Style.RESET_ALL)
                stop(1)
        if deadline < datetime.datetime.now().timestamp():
            print(Fore.RED + f"Timed out waiting for {service} to become healthy" + Style.RESET_ALL)
            if container_id:
                report_container_state(container_id, service)
            else:
                print(f"  {service}: compose has not created a container")
            stop(1)
        time.sleep(1)

def print_logs():
    print("Printing logs ...")
    #Iterating through docker container inspect list and print logs
    for container in containers.values():
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

# Some suites need test accounts present before Dovecot starts its one-time
# mailbox migration. Start Admin and its dependencies, wait for its health,
# then seed the accounts before starting the rest of the stack.
if os.path.isdir(setup_path):
    sys.stdout.flush()
    print(subprocess.check_output(f"docker compose -f {compose_file} up -d admin", shell=True).decode())
    admin_deadline=datetime.datetime.now()+datetime.timedelta(minutes=timeout)
    admin_deadline=calendar.timegm(admin_deadline.timetuple())
    wait_for_service_health("admin", admin_deadline)
    for setup_file in sorted(os.listdir(setup_path)):
        setup_file_path = os.path.join(setup_path, setup_file)
        try:
            if setup_file.endswith(".py"):
                print(subprocess.check_output("python3 " + setup_file_path, shell=True).decode())
            elif setup_file.endswith(".sh"):
                print(subprocess.check_output("./" + setup_file_path, shell=True).decode())
        except subprocess.CalledProcessError as e:
            sys.stderr.write("[ERROR]: output = %s, error code = %s\n" % (e.output.decode(), e.returncode))
            stop(1)

# Start up containers
sys.stdout.flush()
print(subprocess.check_output(f"docker compose -f {compose_file} up -d", shell=True).decode())
print()
print(subprocess.check_output("docker ps -a", shell=True).decode())
print()
# Image pulls and container creation happen during `compose up`; start the
# health-check timeout only once those have completed.
deadline=datetime.datetime.now()+datetime.timedelta(minutes=timeout)
deadline=calendar.timegm(deadline.timetuple())
print(f"Waiting up to {timeout} minutes for compose services to become healthy.")
while not health_checks(deadline):
    sys.stdout.flush()
    time.sleep(1)
# The suite's hooks run only after the compose stack is healthy. In particular,
# the Admin API is ready before any tests that call it begin.
print()
hooks()
print()
stop(0)
