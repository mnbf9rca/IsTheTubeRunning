import { describe, expect, test } from '@jest/globals'
//import { MongoServerError, ErrorDescription } from 'mongodb'
import * as mongo from '../mongo.client';
import config = require('../../utils/config');




describe('test mongo.client with actual database connection', () => {
  afterEach(async () => {
    console.log("closing connection in mongo client afterEach")
    await mongo.close()
  }, 10000)
  test('mongo.GetInstance() returns a database instance', async () => {
    const returned_db = await mongo.GetDbInstance();
    expect(returned_db).toBeDefined();
    expect(config.graph_database_name).toBeDefined();
    expect(returned_db.databaseName).toBe(config.graph_database_name)
  }, 10000)
  test('mongo.GetInstance(password) rejects on invalid password', async () => {
    console.log("closing connection in test test mongo.GetInstance(password) rejects on invalid password")
    await mongo.close()
    /*
    // not sure if i need this - matching the error message is probably enough
    const err_desc: ErrorDescription = {
      message: 'bad auth : authentication failed',
      errmsg: 'bad auth : authentication failed',
      errorLabels:[ 'HandshakeError','ResetPool'],
    }
    await expect(mongo.GetInstance('invalidpassword')).rejects.toThrowError(new MongoServerError(err_desc)) //.toContain('authentication failed')
    */
    await expect(mongo.GetDbInstance('invalidpassword')).rejects.toThrowError('bad auth : authentication failed')

  }, 10000)
})