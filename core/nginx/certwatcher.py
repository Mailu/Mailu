#!/usr/bin/env python3
"""
Certificate watcher which reloads nginx or reconfigures it, depending on what
happens to externally supplied certificates. Only executed by start.py in case
of TLS_FLAVOR=[mail, cert]
"""

from os.path import exists, split as path_split, join as path_join
from os import system, getenv
import time
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler, FileDeletedEvent, \
    FileCreatedEvent, FileModifiedEvent, FileMovedEvent

class ChangeHandler(FileSystemEventHandler):
    "watchdog-handler listening on any event, executing the correct configuration/reload steps"

    def __init__(self, cert_path, keypair_path):
        "Initialize a new changehandler"""
        super().__init__()
        self.cert_path = cert_path
        self.keypair_path = keypair_path

    @staticmethod
    def reload_nginx():
        "merely reload nginx without re-configuring everything"
        if exists("/var/run/nginx.pid"):
            print("Reloading a running nginx")
            system("nginx -s reload")

    @staticmethod
    def reexec_config():
        "execute a reconfiguration of the system, which also reloads"
        print("Reconfiguring system")
        system("/config.py")

    def on_any_event(self, event):
        "event-listener checking if the affected files are the cert-files we're interested in"
        if event.is_directory:
            return

        filename = event.src_path
        if isinstance(event, FileMovedEvent):
            filename = event.dest_path

        if filename in [self.cert_path, self.keypair_path]:
            # all cases except for FileModified need re-configure
            if isinstance(event, (FileCreatedEvent, FileMovedEvent, FileDeletedEvent)):
                ChangeHandler.reexec_config()
            # file modification needs only a nginx reload without config.py
            elif isinstance(event, FileModifiedEvent):
                ChangeHandler.reload_nginx()
        # cert files have been moved away, re-configure
        elif isinstance(event, FileMovedEvent) and event.src_path in [self.cert_path, self.keypair_path]:
            ChangeHandler.reexec_config()


if __name__ == '__main__':
    cert_path = path_join("/certs/", getenv("TLS_CERT_FILENAME", default="cert.pem"))
    cert_dir = path_split(cert_path)[0]
    keypair_path = path_join("/certs/", getenv("TLS_KEYPAIR_FILENAME", default="key.pem"))
    keypair_dir = path_split(keypair_path)[0]

    observer = PollingObserver()
    handler = ChangeHandler(cert_path, keypair_path)
    observer.schedule(handler, cert_dir, recursive=False)
    if keypair_dir != cert_dir:
       observer.schedule(handler, keypair_dir, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
