"""Add an address book for existing users who have none, then run Radicale."""
import os

from radicale import config, storage


def provision_addressbooks(configuration):
    backend = storage.load(configuration)
    with backend.acquire_lock("w"):
        principals = list(backend.discover("/", depth="1"))
        for principal in principals:
            if not isinstance(principal, storage.BaseCollection) or not principal.path:
                continue
            path = "/" + principal.path.strip("/") + "/"
            collections = list(backend.discover(path, depth="1"))
            if any(isinstance(collection, storage.BaseCollection)
                   and collection.get_meta("tag") == "VADDRESSBOOK"
                   for collection in collections):
                continue
            # Never replace an existing collection, even if it has another type.
            if not list(backend.discover(path + "contacts/")):
                backend.create_collection(path + "contacts/", props={
                    "tag": "VADDRESSBOOK", "D:displayname": "Contacts",
                })


if __name__ == "__main__":
    provision_addressbooks(config.load([("/radicale.conf", False)]))
    os.execvp("radicale", ["radicale", "-S", "-C", "/radicale.conf"])
