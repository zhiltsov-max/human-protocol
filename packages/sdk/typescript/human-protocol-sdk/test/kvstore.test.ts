/* eslint-disable @typescript-eslint/no-explicit-any */
import { ethers } from 'ethers';
import { beforeAll, beforeEach, describe, expect, test, vi } from 'vitest';
import { NETWORKS } from '../src/constants';
import { ChainId } from '../src/enums';
import {
  ErrorInvalidAddress,
  ErrorKVStoreArrayLength,
  ErrorKVStoreEmptyKey,
  ErrorProviderDoesNotExist,
  ErrorSigner,
  ErrorUnsupportedChainID,
} from '../src/error';
import { KVStoreClient } from '../src/kvstore';
import { NetworkData } from '../src/types';
import { DEFAULT_GAS_PAYER_PRIVKEY } from './utils/constants';

vi.mock('../src/init');

describe('KVStoreClient', () => {
  let mockProvider: any,
    mockSigner: any,
    network: NetworkData | undefined,
    kvStoreClient: any,
    mockKVStoreContract: any;

  beforeAll(async () => {
    const provider = new ethers.providers.JsonRpcProvider();
    mockProvider = {
      ...provider,
      getNetwork: vi.fn().mockReturnValue({ chainId: ChainId.LOCALHOST }),
    };
    mockSigner = {
      ...provider.getSigner(),
      provider: {
        ...mockProvider,
      },
      getAddress: vi.fn().mockReturnValue(ethers.constants.AddressZero),
    };
    network = NETWORKS[ChainId.LOCALHOST];
  });

  beforeEach(async () => {
    kvStoreClient = await KVStoreClient.build(mockSigner);
    mockKVStoreContract = {
      ...kvStoreClient.contract,
      set: vi.fn(),
      setBulk: vi.fn(),
      get: vi.fn(),
      address: network?.kvstoreAddress,
    };
    kvStoreClient.contract = mockKVStoreContract;
  });

  describe('build', () => {
    test('should create a new instance of KVStoreClient with a Signer', async () => {
      const kvStoreClient = await KVStoreClient.build(mockSigner);

      expect(kvStoreClient).toBeInstanceOf(KVStoreClient);
    });

    test('should create a new instance of KVStoreClient with a Provider', async () => {
      const provider = ethers.getDefaultProvider();

      const kvStoreClient = await KVStoreClient.build(provider);

      expect(kvStoreClient).toBeInstanceOf(KVStoreClient);
    });

    test('should throw an error if Signer provider does not exist', async () => {
      const signer = new ethers.Wallet(DEFAULT_GAS_PAYER_PRIVKEY);

      await expect(KVStoreClient.build(signer)).rejects.toThrow(
        ErrorProviderDoesNotExist
      );
    });

    test('should throw an error if the chain ID is unsupported', async () => {
      const provider = ethers.getDefaultProvider();

      vi.spyOn(provider, 'getNetwork').mockResolvedValue({
        chainId: 1337,
      } as any);

      await expect(KVStoreClient.build(provider)).rejects.toThrow(
        ErrorUnsupportedChainID
      );
    });
  });

  describe('set', () => {
    test('should throw an error if key is empty', async () => {
      const setSpy = vi.spyOn(kvStoreClient, 'set');
      await expect(kvStoreClient.set('', 'test')).rejects.toThrow(
        ErrorKVStoreEmptyKey
      );
      expect(setSpy).toHaveBeenCalledWith('', 'test');
    });

    test('should set the key-value pair if both key and value are provided', async () => {
      mockKVStoreContract.set.mockResolvedValue(null);
      expect(kvStoreClient.set('key1', 'value1')).resolves.toBeUndefined();
      expect(mockKVStoreContract.set).toHaveBeenCalledWith('key1', 'value1');
    });

    test('should throw an error when attempting to set a value without signer', async () => {
      kvStoreClient = await KVStoreClient.build(mockProvider);

      await expect(kvStoreClient.set('key1', 'value1')).rejects.toThrow(
        ErrorSigner
      );
    });

    test('should throw an error when a network error occurs', async () => {
      mockKVStoreContract.set.mockRejectedValue(
        new Error('could not detect network')
      );

      await expect(kvStoreClient.set('key1', 'value1')).rejects.toThrow(
        Error('Failed to set value: could not detect network')
      );

      expect(mockKVStoreContract.set).toHaveBeenCalledWith('key1', 'value1');
    });
  });

  describe('setBulk', () => {
    test('should throw an error if keys and values arrays are not of the same length', async () => {
      const setBulkSpy = vi.spyOn(kvStoreClient, 'setBulk');
      await expect(
        kvStoreClient.setBulk(['key1', 'key2'], ['value1'])
      ).rejects.toThrow(ErrorKVStoreArrayLength);
      expect(setBulkSpy).toHaveBeenCalledWith(['key1', 'key2'], ['value1']);
    });

    test('should throw an error if any of the keys is empty', async () => {
      const setBulkSpy = vi.spyOn(kvStoreClient, 'setBulk');
      await expect(
        kvStoreClient.setBulk(['key1', ''], ['value1', 'value2'])
      ).rejects.toThrow(ErrorKVStoreEmptyKey);
      expect(setBulkSpy).toHaveBeenCalledWith(
        ['key1', ''],
        ['value1', 'value2']
      );
    });

    test('should set the key-value pairs if both keys and values arrays are provided correctly', async () => {
      mockKVStoreContract.setBulk.mockResolvedValue(null);
      expect(
        kvStoreClient.setBulk(['key1', 'key2'], ['value1', 'value2'])
      ).resolves.resolves.toBeUndefined();
      expect(mockKVStoreContract.setBulk).toHaveBeenCalledWith(
        ['key1', 'key2'],
        ['value1', 'value2']
      );
    });

    test('should throw an error when attempting to set values without signer', async () => {
      kvStoreClient = await KVStoreClient.build(mockProvider);

      await expect(
        kvStoreClient.setBulk(['key1', 'key2'], ['value1', 'value2'])
      ).rejects.toThrow(ErrorSigner);
    });

    test('should throw an error if a network error occurs', async () => {
      mockKVStoreContract.setBulk.mockRejectedValue(
        new Error('could not detect network')
      );
      await expect(
        kvStoreClient.setBulk(['key1', 'key2'], ['value1', 'value2'])
      ).rejects.toThrow(
        new Error('Failed to set bulk values: could not detect network')
      );
      expect(mockKVStoreContract.setBulk).toHaveBeenCalledWith(
        ['key1', 'key2'],
        ['value1', 'value2']
      );
    });
  });

  describe('get', () => {
    test('should throw an error if key is empty', async () => {
      await expect(
        kvStoreClient.get('0x42d75a16b04a02d1abd7f2386b1c5b567bc7ef71', '')
      ).rejects.toThrow(ErrorKVStoreEmptyKey);
    });

    test('should throw an error if address is not valid', async () => {
      await expect(
        kvStoreClient.get('invalid_address', 'key1')
      ).rejects.toThrow(ErrorInvalidAddress);
    });

    test('should return empty string if both address and key are valid and address does not set any value', async () => {
      const getSpy = vi.spyOn(kvStoreClient, 'get').mockResolvedValue('');
      const result = await kvStoreClient.get(
        '0x42d75a16b04a02d1abd7f2386b1c5b567bc7ef71',
        'key1'
      );
      expect(result).toBe('');
      expect(getSpy).toHaveBeenCalledWith(
        '0x42d75a16b04a02d1abd7f2386b1c5b567bc7ef71',
        'key1'
      );
    });

    test('should return value if both address and key are valid and address set a value', async () => {
      mockKVStoreContract.get.mockResolvedValue('value1');

      const getSpy = vi.spyOn(kvStoreClient, 'get');
      const result = await kvStoreClient.get(
        '0x42d75a16b04a02d1abd7f2386b1c5b567bc7ef71',
        'key1'
      );
      expect(result).toBe('value1');
      expect(getSpy).toHaveBeenCalledWith(
        '0x42d75a16b04a02d1abd7f2386b1c5b567bc7ef71',
        'key1'
      );
      expect(mockKVStoreContract.get).toHaveBeenCalledWith(
        '0x42d75a16b04a02d1abd7f2386b1c5b567bc7ef71',
        'key1'
      );
    });

    test('should throw an error if a network error occurs', async () => {
      mockKVStoreContract.get.mockRejectedValue(
        new Error('could not detect network')
      );

      await expect(
        kvStoreClient.get('0x42d75a16b04a02d1abd7f2386b1c5b567bc7ef71', 'key1')
      ).rejects.toThrow(Error('Failed to get value: could not detect network'));

      expect(mockKVStoreContract.get).toHaveBeenCalledWith(
        '0x42d75a16b04a02d1abd7f2386b1c5b567bc7ef71',
        'key1'
      );
    });
  });
});
