from src.core.manifest import TaskManifest


def parse_manifest(manifest: dict) -> TaskManifest:
    return TaskManifest.parse_obj(manifest)
