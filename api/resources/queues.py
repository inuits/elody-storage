import app

from storage.storagemanager import StorageManager


def __is_malformed_message(data, fields):
    if not all(x in data for x in fields):
        app.logger.error(f"Message malformed: missing one of {fields}")
        return True
    return False


@app.rabbit.queue(["dams.file_uploaded", "dams.mediafile_changed"])
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
    if old_mediafile and not storage.is_metadata_updated(
        old_mediafile.get("metadata", []), mediafile["metadata"]
    ):
        return
    # storage.add_exif_data(mediafile)


@app.rabbit.queue("dams.file_scanned")
def remove_infected_file_from_storage(routing_key, body, message_id):
    data = body["data"]
    if __is_malformed_message(data, ["mediafile_id", "clamav_version", "infected"]):
        return
    if data["infected"]:
        StorageManager().get_storage_engine().delete_files([data["filename"]])


@app.rabbit.queue("dams.mediafile_deleted")
def remove_file_from_storage(routing_key, body, message_id):
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
