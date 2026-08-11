import app  # noqa: F401 -- imported first to avoid a circular import in s3store
from storage.s3store import S3StorageManager

extract = S3StorageManager._check_keys_and_extract_creation_dates


def test_exif_date_format_is_parsed():
    exif_data = [{"key": "DateTimeOriginal", "value": "2025:07:28 15:38:50"}]

    assert extract(None, exif_data) == "2025-07-28T15:38:50"


def test_date_time_original_takes_precedence_over_digitized():
    exif_data = [
        {"key": "DateTimeDigitized", "value": "2025:07:28 15:38:50"},
        {"key": "DateTimeOriginal", "value": "2001:01:01 01:01:01"},
    ]

    assert extract(None, exif_data) == "2001-01-01T01:01:01"


def test_no_creation_date_returns_none():
    assert extract(None, []) is None
    assert extract(None, [{"key": "Make", "value": "Apple"}]) is None
    assert extract(None, [{"key": "DateTimeOriginal", "value": "not a date"}]) is None
