#!/usr/bin/python3
"""
Certificate watcher which reloads nginx or reconfigures it, depending on what
happens to externally supplied certificates. Only executed by start.py in case
of TLS_FLAVOR=[mail, cert]
"""

from os.path import exists, split as path_split
from os import system
import time
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler, FileDeletedEvent, \
    FileCreatedEvent, FileModifiedEvent, FileMovedEvent

class ChangeHandler(FileSystemEventHandler):
    "watchdog-handler listening on any event, executing the correct configuration/reload steps"
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

        filename = path_split(event.src_path)[-1]
        if isinstance(event, FileMovedEvent):
            filename = path_split(event.dest_path)[-1]

        if filename in ['cert.pem', 'key.pem']:
            # all cases except for FileModified need re-configure
            if isinstance(event, (FileCreatedEvent, FileMovedEvent, FileDeletedEvent)):
                ChangeHandler.reexec_config()
            # file modification needs only a nginx reload without config.py
            elif isinstance(event, FileModifiedEvent):
                ChangeHandler.reload_nginx()
        # cert files have been moved away, re-configure
        elif isinstance(event, FileMovedEvent) and path_split(event.src_path)[-1] in ['cert.pem', 'key.pem']:
            ChangeHandler.reexec_config()


if __name__ == '__main__':
    observer = PollingObserver()
    handler = ChangeHandler()
    observer.schedule(handler, "/certs", recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
