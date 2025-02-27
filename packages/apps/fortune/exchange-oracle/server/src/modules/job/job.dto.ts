import { ApiProperty } from '@nestjs/swagger';
import { ChainId } from '@human-protocol/sdk';
import { IsEnum, IsString } from 'class-validator';
import { IsValidEthereumAddress } from '../../common/validators';

export class ManifestDto {
  title: string;
  description: string;
  fortunesRequested: number;
  fundAmount: number;
}

export class JobDetailsDto {
  escrowAddress: string;
  chainId: number;
  manifest: ManifestDto;
}

export class SolveJobDto {
  @ApiProperty()
  @IsString()
  @IsValidEthereumAddress()
  public escrowAddress: string;

  @ApiProperty({
    enum: ChainId,
  })
  @IsEnum(ChainId)
  public chainId: ChainId;

  @ApiProperty()
  @IsString()
  @IsValidEthereumAddress()
  public workerAddress: string;

  @ApiProperty()
  @IsString()
  public solution: string;
}
