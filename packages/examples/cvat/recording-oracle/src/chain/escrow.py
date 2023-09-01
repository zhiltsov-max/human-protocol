import json
from human_protocol_sdk.constants import Status
from human_protocol_sdk.escrow import EscrowClient
from human_protocol_sdk.storage import StorageClient

from src.chain.web3 import get_web3
from src.core.types import TaskType


def get_escrow_manifest(chain_id: int, escrow_address: str) -> dict:
    # web3 = get_web3(chain_id)
    # escrow_client = EscrowClient(web3)

    # manifest_url = escrow_client.get_manifest_url(escrow_address)

    # return json.loads(
    #     (StorageClient.download_file_from_url(manifest_url)).decode("utf-8")
    # )

    # TODO: remove mock
    return {
        "data": {
            "data_url": "http://datasets.minio:9010",
        },
        "annotation": {
            "labels": [{"name": "cat"}],
            "type": "IMAGE_BOXES",
            "job_size": 3,
        },
        "validation": {
            "val_size": 2,
            "min_quality": 0.9,
            "gt_url": "http://datasets.minio:9010/gt_annotations_coco/annotations/instances_default.json",
        },
        "job_bounty": "10.2",
    }


def validate_escrow(chain_id: int, escrow_address: str):
    # TODO: remove mock
    return

    web3 = get_web3(chain_id)
    escrow_client = EscrowClient(web3)

    if escrow_client.get_balance(escrow_address) == 0:
        raise ValueError("Escrow doesn't have funds")

    escrow_status = escrow_client.get_status(escrow_address)
    if escrow_status != Status.Pending:
        raise ValueError(
            f"Escrow is not in a Pending state. Current state: {escrow_status.name}"
        )

    manifest_url = escrow_client.get_manifest_url(escrow_address)

    manifest = json.loads(
        (StorageClient.download_file_from_url(manifest_url)).decode("utf-8")
    )
    job_type = manifest["requestType"]
    if job_type not in TaskType.__members__.values():
        raise ValueError(f"Oracle doesn't support job type {job_type}")


def store_results(chain_id: int, escrow_address: str, url: str, hash: str) -> None:
    web3 = get_web3(chain_id)
    escrow_client = EscrowClient(web3)

    escrow_client.store_results(escrow_address, url, hash)


def get_reputation_oracle_address(chain_id: int, escrow_address: str) -> str:
    web3 = get_web3(chain_id)
    escrow_client = EscrowClient(web3)

    reputation_oracle_address = escrow_client.get_reputation_oracle_address(
        escrow_address
    )

    return reputation_oracle_address
