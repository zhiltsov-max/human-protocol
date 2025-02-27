import { BigNumber } from 'ethers';
import { EscrowStatus } from './types';

export interface IAllocation {
  escrowAddress: string;
  staker: string;
  tokens: BigNumber;
  createdAt: BigNumber;
  closedAt: BigNumber;
}

export interface IReward {
  escrowAddress: string;
  amount: BigNumber;
}

export interface IStaker {
  tokensStaked: BigNumber;
  tokensAllocated: BigNumber;
  tokensLocked: BigNumber;
  tokensLockedUntil: BigNumber;
  tokensAvailable: BigNumber;
}

export interface IEscrowsFilter {
  address?: string;
  role?: number;
  status?: EscrowStatus;
  from?: Date;
  to?: Date;
}

export interface IEscrowConfig {
  recordingOracle: string;
  reputationOracle: string;
  recordingOracleFee: BigNumber;
  reputationOracleFee: BigNumber;
  manifestUrl: string;
  manifestHash: string;
}

export interface IKeyPair {
  privateKey: string;
  publicKey: string;
  passphrase: string;
  revocationCertificate?: string;
}
