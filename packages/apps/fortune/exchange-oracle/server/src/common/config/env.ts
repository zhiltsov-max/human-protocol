import * as Joi from 'joi';

export const ConfigNames = {
  HOST: 'HOST',
  PORT: 'PORT',
  WEB3_PRIVATE_KEY: 'WEB3_PRIVATE_KEY',
};

export const envValidator = Joi.object({
  HOST: Joi.string().default('localhost'),
  PORT: Joi.string().default(3002),
  WEB3_PRIVATE_KEY: Joi.string().required(),
});
