import app

from storage.storagemanager import StorageManager


@app.rabbit.queue("dams.file_uploaded")
def handle_file_uploaded(routing_key, body, message_id):
    data = body["data"]
    if any(x not in data for x in ["mediafile"]):
        app.logger.error("Message malformed: missing 'mediafile'")
        return
    mediafile = data["mediafile"]
    if "mimetype" in mediafile and "metadata" in mediafile and mediafile["metadata"]:
        StorageManager().get_storage_engine().add_exif_data(mediafile)


@app.rabbit.queue("dams.file_scanned")
def remove_infected_file(routing_key, body, message_id):
    data = body["data"]
    if any(x not in data for x in ["mediafile_id", "clamav_version", "infected"]):
        app.logger.error(
            "Message malformed: missing 'mediafile_id', 'clamav_version' or 'infected'"
        )
        return
    if data["infected"]:
        StorageManager().get_storage_engine().delete_files([data["filename"]])


@app.rabbit.queue("dams.mediafile_changed")
def handle_mediafile_updated(routing_key, body, message_id):
    data = body["data"]
    if any(x not in data for x in ["old_mediafile", "mediafile"]):
        app.logger.error("Message malformed: missing 'old_mediafile' or 'mediafile'")
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
    if any(x not in data for x in ["mediafile", "linked_entities"]):
        app.logger.error("Message malformed: missing 'mediafile' or 'linked_entities'")
        return
    files = [data["mediafile"]["filename"]]
    if "transcode_filename" in data["mediafile"]:
        files.append(data["mediafile"]["transcode_filename"])
    try:
        StorageManager().get_storage_engine().delete_files(files)
    except Exception as ex:
        app.logger.error(f"Deleting {files} failed with: {ex}")
