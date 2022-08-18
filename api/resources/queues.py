import app

from storage.storagemanager import StorageManager


@app.rabbit.queue("dams.file_uploaded")
def handle_file_uploaded(routing_key, body, message_id):
    mediafile = body["data"]["mediafile"]
    if (
        "mimetype" not in mediafile
        or "metadata" not in mediafile
        or not len(mediafile["metadata"])
    ):
        return
    # storage.add_exif_data(mediafile)


@app.rabbit.queue("dams.mediafile_changed")
def handle_mediafile_updated(routing_key, body, message_id):
    old_mediafile = body["data"]["old_mediafile"]
    mediafile = body["data"]["mediafile"]
    if "mimetype" not in mediafile or "metadata" not in mediafile:
        return
    if (
        "metadata" in old_mediafile
        and not StorageManager()
        .get_storage_engine()
        .is_metadata_updated(old_mediafile["metadata"], mediafile["metadata"])
    ):
        return
    # storage.add_exif_data(mediafile)


@app.rabbit.queue("dams.mediafile_deleted")
def handle_mediafile_deleted(routing_key, body, message_id):
    data = body["data"]
    if "mediafile" not in data or "linked_entities" not in data:
        return
    files = [data["mediafile"]["filename"]]
    if "transcode_filename" in data["mediafile"]:
        files.append(data["mediafile"]["transcode_filename"])
    try:
        StorageManager().get_storage_engine().delete_files(files)
    except Exception as ex:
        app.logger.error(f"Deleting {files} failed with: {ex}")
