from boto3 import client
from botocore.config import Config
from contextlib import closing
from elody.error_codes import ErrorCode, get_error_code, get_write
from elody.exceptions import DuplicateFileException
from io import BytesIO
from mypy_boto3_s3.client import S3Client
from os import getenv


class StreamedS3Store:
    def __init__(self):
        self.s3: S3Client = client(
            "s3",
            endpoint_url=getenv("MINIO_ENDPOINT"),
            aws_access_key_id=getenv("MINIO_ACCESS_KEY"),
            aws_secret_access_key=getenv("MINIO_SECRET_KEY"),
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 10, "mode": "standard"},
            ),
        )
        self.s3_public: S3Client = client(
            "s3",
            endpoint_url=getenv("MINIO_ENDPOINT_EXT", "http://minio.localhost:8000"),
            aws_access_key_id=getenv("MINIO_ACCESS_KEY"),
            aws_secret_access_key=getenv("MINIO_SECRET_KEY"),
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 10, "mode": "standard"},
            ),
        )

    def init_stream(self, *, key: str):
        return self.s3.create_multipart_upload(Bucket=self.__get_bucket(), Key=key)[
            "UploadId"
        ]

    def sign_chunk(self, *, stream_id: str, key: str, chunk_sequence: int):
        return self.s3_public.generate_presigned_url(
            ClientMethod="upload_part",
            Params={
                "Bucket": self.__get_bucket(),
                "Key": key,
                "PartNumber": chunk_sequence,
                "UploadId": stream_id,
            },
            ExpiresIn=3600,
        )

    def complete_stream(
        self,
        *,
        stream_id: str,
        key: str,
        chunks_info: list[dict],
        file_info: dict,
        legacy_store,
    ):
        filename = f"{file_info['md5sum']}-{file_info['name']}"
        try:
            legacy_store.check_file_exists(
                filename, file_info["md5sum"], bucket_name=self.__get_bucket()
            )
            is_duplicate = False
        except DuplicateFileException:
            self.abort_stream(stream_id=stream_id, key=key)
            is_duplicate = True
        else:
            parts = [
                {
                    "ETag": chunk_info["hash"],
                    "PartNumber": int(chunk_info["sequence_number"]),
                }
                for chunk_info in chunks_info
            ]
            self.s3.complete_multipart_upload(
                Bucket=self.__get_bucket(),
                Key=key,
                UploadId=stream_id,
                MultipartUpload={
                    "Parts": sorted(
                        parts, key=lambda part: part["PartNumber"]
                    )  # pyright: ignore
                },
            )
            self.s3.copy_object(
                Bucket=self.__get_bucket(),
                Key=filename,
                CopySource={"Bucket": self.__get_bucket(), "Key": key},
            )
            self.s3.delete_object(Bucket=self.__get_bucket(), Key=key)

        response = self.s3.get_object(Bucket=self.__get_bucket(), Key=filename)
        with response["Body"] as file_stream:
            header_data = file_stream.read(500 * (1024**2))
            with closing(BytesIO(header_data)) as file_part:
                file_part.name = file_info["name"]
                legacy_store.upload_file(
                    file=file_part,
                    mediafile_id=key,
                    key=filename,
                    ticket=None,
                    parent_job_id=None,
                    md5sum=file_info["md5sum"],
                    skip_s3_upload=True,
                    bucket_name=self.__get_bucket(),
                    is_duplicate=is_duplicate,
                )

    def abort_stream(self, *, stream_id: str, key: str):
        try:
            self.s3.abort_multipart_upload(
                Bucket=self.__get_bucket(), Key=key, UploadId=stream_id
            )
        except self.s3.exceptions.NoSuchUpload:
            pass

    def __get_bucket(self):
        if bucket := getenv("MINIO_BUCKET"):
            return bucket
        raise Exception(
            f"{get_error_code(ErrorCode.NO_BUCKET_SPECIFIED, get_write())} No bucket for upload was specified"
        )
