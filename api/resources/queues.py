from os import getenv

from app import logger
from rabbit import get_rabbit
from storage.storagemanager import StorageManager

queue_type = getenv("QUEUE_TYPE", "classic")
ROUTING_KEY_PREFIX = getenv("ROUTING_KEY_PREFIX", "dams")


def __is_malformed_message(data, fields):
    if not all(x in data for x in fields):
        logger.error(f"Message malformed: missing one of {fields}")
        return True
    return False


def __argument_wrapper(*, queue_name, routing_key):
    arguments = {"routing_key": routing_key}
    if getenv("AMQP_MANAGER", "amqpstorm_flask") == "amqpstorm_flask":
        arguments["queue_name"] = queue_name
        if queue_type:
            arguments["queue_arguments"] = {"x-queue-type": queue_type}
    return arguments


@get_rabbit().queue(
    **__argument_wrapper(
        queue_name="basic.add.exif.data.to.image",
        routing_key=[
            f"{ROUTING_KEY_PREFIX}.file_uploaded.#",
            f"{ROUTING_KEY_PREFIX}.mediafile_changed",
        ],
    ),
)
def add_exif_data_to_image(routing_key, body, message_id):
    data = body["data"]
    required = ["mediafile"]
    if routing_key == "dams.mediafile_changed":
        required.append("old_mediafile")
    if __is_malformed_message(data, required):
        return
    mediafile = data["mediafile"]
    old_mediafile = data.get("old_mediafile")
    if not mediafile.get("mimetype") or not mediafile.get("metadata"):
        return
    storage = StorageManager().get_storage_engine()
    if old_mediafile and not storage.is_metadata_updated(old_mediafile, mediafile):
        return
    # storage.add_exif_data(mediafile)


@get_rabbit().queue(
    **__argument_wrapper(
        queue_name="basic.remove.infected.file.from.storage",
        routing_key=f"{ROUTING_KEY_PREFIX}.file_scanned",
    ),
)
def remove_infected_file_from_storage(routing_key, body, message_id):
    data = body["data"]
    if __is_malformed_message(data, ["mediafile_id", "clamav_version", "infected"]):
        return
    if data["infected"]:
        StorageManager().get_storage_engine().delete_files([data["filename"]])


@get_rabbit().queue(
    **__argument_wrapper(
        queue_name="basic.remove.file.from.storage",
        routing_key=f"{ROUTING_KEY_PREFIX}.mediafile_deleted",
    ),
)
def remove_file_from_storage(routing_key, body, message_id):
    data = body["data"]
    if __is_malformed_message(data, ["mediafile", "linked_entities"]):
        return
    files = [data["mediafile"]["filename"]]
    if "transcode_filename" in data["mediafile"]:
        files.append(data["mediafile"]["transcode_filename"])
    try:
        StorageManager().get_storage_engine().delete_files(files)
    except Exception as ex:  # noqa: BLE001
        logger.error(f"Deleting {files} failed with: {ex}")
