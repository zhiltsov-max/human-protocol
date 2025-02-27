import { Module } from '@nestjs/common';

import { PaymentService } from './payment.service';
import { CurrencyService } from './currency.service';
import { MinioModule } from 'nestjs-minio-client';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { PaymentEntity } from './payment.entity';
import { TypeOrmModule } from '@nestjs/typeorm';
import { PaymentController } from './payment.controller';
import { PaymentRepository } from './payment.repository';
import { HttpModule } from '@nestjs/axios';

@Module({
  imports: [
    HttpModule,
    TypeOrmModule.forFeature([PaymentEntity]),
    ConfigModule,
    MinioModule.registerAsync({
      imports: [ConfigModule],
      inject: [ConfigService],
      useFactory: (configService: ConfigService) => {
        return {
          endPoint: configService.get('S3_HOST', '127.0.0.1'),
          port: Number(configService.get<number>('S3_PORT', 9000)),
          useSSL: false,
          accessKey: configService.get('S3_ACCESS_KEY', 'access-key'),
          secretKey: configService.get('S3_SECRET_KEY', 'secrete-key'),
        };
      },
    }),
  ],
  controllers: [PaymentController],
  providers: [PaymentService, PaymentRepository, CurrencyService],
  exports: [PaymentService],
})
export class PaymentModule {}
