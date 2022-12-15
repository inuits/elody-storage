import app

from storage.storagemanager import StorageManager


def __is_malformed_message(data, fields):
    if not all(x in data for x in fields):
        app.logger.error(f"Message malformed: missing one of {fields}")
        return True
    return False


@app.rabbit.queue("dams.file_uploaded")
def handle_file_uploaded(routing_key, body, message_id):
    data = body["data"]
    if __is_malformed_message(data, ["mediafile"]):
        return
    mediafile = data["mediafile"]
    if "mimetype" in mediafile and "metadata" in mediafile and mediafile["metadata"]:
        StorageManager().get_storage_engine().add_exif_data(mediafile)


@app.rabbit.queue("dams.file_scanned")
def remove_infected_file(routing_key, body, message_id):
    data = body["data"]
    if __is_malformed_message(data, ["mediafile_id", "clamav_version", "infected"]):
        return
    if data["infected"]:
        StorageManager().get_storage_engine().delete_files([data["filename"]])


@app.rabbit.queue("dams.mediafile_changed")
def handle_mediafile_updated(routing_key, body, message_id):
    data = body["data"]
    if __is_malformed_message(data, ["old_mediafile", "mediafile"]):
        return
    old_mediafile = data["old_mediafile"]
    mediafile = data["mediafile"]
    if "mimetype" not in mediafile or "metadata" not in mediafile:
        return
    storage = StorageManager().get_storage_engine()
    if "metadata" not in old_mediafile or storage.is_metadata_updated(
        old_mediafile["metadata"], mediafile["metadata"]
    ):
        storage.add_exif_data(mediafile)


@app.rabbit.queue("dams.mediafile_deleted")
def handle_mediafile_deleted(routing_key, body, message_id):
    data = body["data"]
    if __is_malformed_message(data, ["mediafile", "linked_entities"]):
        return
    files = [data["mediafile"]["filename"]]
    if "transcode_filename" in data["mediafile"]:
        files.append(data["mediafile"]["transcode_filename"])
    try:
        StorageManager().get_storage_engine().delete_files(files)
    except Exception as ex:
        app.logger.error(f"Deleting {files} failed with: {ex}")
