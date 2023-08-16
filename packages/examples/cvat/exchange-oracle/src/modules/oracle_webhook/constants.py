from enum import Enum, EnumMeta


class MyEnumMeta(EnumMeta):
    def __contains__(cls, item):
        return isinstance(item, cls) or item in [
            v.value for v in cls.__members__.values()
        ]


class OracleWebhookSenderType(str, Enum, metaclass=MyEnumMeta):
    job_launcher = "job_launcher"
    recording_oracle = "recording_oracle"


class JobLauncherEventType(str, Enum, metaclass=MyEnumMeta):
    escrow_created = "escrow_created"
    escrow_canceled = "escrow_canceled"


class RecordingOracleEventType(str, Enum, metaclass=MyEnumMeta):
    task_completed = "task_completed"
    task_rejected = "task_rejected"


class OracleWebhookStatuses(str, Enum, metaclass=MyEnumMeta):
    pending = "pending"
    completed = "completed"
    failed = "failed"
