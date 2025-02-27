import { Column, Entity, OneToMany } from 'typeorm';
import { Exclude } from 'class-transformer';

import { NS } from '../../common/constants';
import { BaseEntity } from '../../database/base.entity';
import { IUser } from '../../common/interfaces';
import { UserStatus, UserType } from '../../common/enums/user';
import { PaymentEntity } from '../payment/payment.entity';
import { JobEntity } from '../job/job.entity';

@Entity({ schema: NS, name: 'user' })
export class UserEntity extends BaseEntity implements IUser {
  @Exclude()
  @Column({ type: 'varchar', select: false })
  public password: string;

  @Column({ type: 'varchar', nullable: true, unique: true })
  public email: string;

  @Column({ type: 'varchar', nullable: true, unique: true })
  public stripeCustomerId: string;

  @Column({ type: 'enum', enum: UserType })
  public type: UserType;

  @Column({
    type: 'enum',
    enum: UserStatus,
  })
  public status: UserStatus;

  @OneToMany(() => JobEntity, (job) => job.user)
  public jobs: JobEntity[];

  @OneToMany(() => PaymentEntity, (payment) => payment.user)
  public payments: PaymentEntity[];
}
