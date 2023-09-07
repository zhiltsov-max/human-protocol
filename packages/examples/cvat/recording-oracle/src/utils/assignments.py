from src.core.manifest import TaskManifest

from hashlib import sha256


def parse_manifest(manifest: dict) -> TaskManifest:
    return TaskManifest.parse_obj(manifest)


def compute_resulting_annotations_hash(data: bytes) -> str:
    return sha256(data, usedforsecurity=False).hexdigest()
