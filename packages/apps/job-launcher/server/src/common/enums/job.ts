export enum JobStatus {
  PENDING = 'PENDING',
  PAID = 'PAID',
  LAUNCHED = 'LAUNCHED',
  COMPLETED = 'COMPLETED',
  FAILED = 'FAILED',
}

export enum JobMode {
  BATCH = 'BATCH',
  DESCRIPTIVE = 'DESCRIPTIVE',
}

export enum JobRequestType {
  IMAGE_LABEL_BINARY = 'IMAGE_LABEL_BINARY',
  FORTUNE = 'FORTUNE',
}
