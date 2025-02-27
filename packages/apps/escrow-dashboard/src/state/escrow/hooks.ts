import { ChainId } from '@human-protocol/sdk';
import { useSelector } from 'react-redux';

import { AppState, useAppDispatch } from '..';
import {
  fetchEscrowAmountsAsync,
  fetchEscrowEventsAsync,
  fetchEscrowStatsAsync,
} from './reducer';
import { EscrowData } from './types';
import { SUPPORTED_CHAIN_IDS, TESTNET_CHAIN_IDS } from 'src/constants';
import { useSlowRefreshEffect } from 'src/hooks/useRefreshEffect';

export const usePollEventsData = () => {
  const dispatch = useAppDispatch();
  const { range } = useSelector((state: AppState) => state.escrow);

  useSlowRefreshEffect(() => {
    dispatch(fetchEscrowEventsAsync(range));
    dispatch(fetchEscrowStatsAsync());
    dispatch(fetchEscrowAmountsAsync());
  }, [dispatch, range]);
};

export const useChainId = () => {
  const escrow = useSelector((state: AppState) => state.escrow);
  return escrow.chainId;
};

export const useEscrowDataByChainID = (): EscrowData => {
  const { escrow, token } = useSelector((state: AppState) => state);
  const { amounts, stats, events, chainId, range } = escrow;

  if (chainId === ChainId.ALL) {
    const escrowData: EscrowData = {
      amount: 0,
      stats: {
        bulkTransferEventCount: 0,
        intermediateStorageEventCount: 0,
        pendingEventCount: 0,
        totalEventCount: 0,
      },
      lastMonthEvents: [],
    };

    SUPPORTED_CHAIN_IDS.forEach((chainId) => {
      if (amounts[chainId]) {
        escrowData.amount += amounts[chainId]!;
      }
      if (stats[chainId]) {
        escrowData.stats.bulkTransferEventCount +=
          stats[chainId]?.bulkTransferEventCount!;
        escrowData.stats.pendingEventCount +=
          stats[chainId]?.pendingEventCount!;
        escrowData.stats.intermediateStorageEventCount +=
          stats[chainId]?.intermediateStorageEventCount!;
        escrowData.stats.totalEventCount += stats[chainId]?.totalEventCount!;
      }
      if (Array.isArray(events[chainId])) {
        events[chainId]?.forEach((e1) => {
          const index = escrowData.lastMonthEvents.findIndex(
            (e) => e.timestamp === e1.timestamp
          );
          if (index >= 0) {
            escrowData.lastMonthEvents[index].dailyBulkTransferEvents +=
              e1.dailyBulkTransferEvents;
            escrowData.lastMonthEvents[index].dailyEscrowAmounts +=
              e1.dailyEscrowAmounts;
            escrowData.lastMonthEvents[index].dailyIntermediateStorageEvents +=
              e1.dailyIntermediateStorageEvents;
            escrowData.lastMonthEvents[index].dailyPendingEvents +=
              e1.dailyPendingEvents;
          } else {
            escrowData.lastMonthEvents.push({ ...e1 });
          }
        });
      }
    });

    escrowData.lastMonthEvents = escrowData.lastMonthEvents
      .sort((x, y) => Number(y.timestamp) - Number(x.timestamp))
      .slice(0, range)
      .reverse();

    return escrowData;
  }

  const escrowData = {
    amount: amounts[chainId] ?? 0,
    stats: stats[chainId] ?? {
      pendingEventCount: 0,
      bulkTransferEventCount: 0,
      intermediateStorageEventCount: 0,
      totalEventCount: 0,
    },
    lastMonthEvents: events[chainId] ?? [],
    totalSupply: TESTNET_CHAIN_IDS.includes(chainId)
      ? token.stats[chainId]?.totalSupply
      : undefined,
  };

  escrowData.lastMonthEvents = [...escrowData.lastMonthEvents]
    .sort((x, y) => Number(y.timestamp) - Number(x.timestamp))
    .slice(0, 30)
    .reverse();
  return escrowData;
};

export const useEscrowDataLoaded = () => {
  const escrow = useSelector((state: AppState) => state.escrow);

  return escrow.eventsLoaded && escrow.amountsLoaded && escrow.statsLoaded;
};
