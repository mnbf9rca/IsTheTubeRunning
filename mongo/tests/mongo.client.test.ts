import { describe, expect, test } from '@jest/globals'
import { MongoClient } from 'mongodb';

//import { MongoServerError, ErrorDescription } from 'mongodb'
import * as mongo from '../mongo';
import * as mongoClient from '../mongo.client';
import config = require('../../utils/config');




describe('test mongo.client with actual database connection', () => {
  afterEach(async () => {
    console.log("closing connection in mongo client afterEach")
    await mongo.close()
  }, 10000)
  test('mongo.GetInstance() returns a database instance', async () => {
    const mongo_client = await mongo.getMongoClient();
    const returned_db = await mongo.getMongoDbFromClient(mongo_client, config.graph_database_name);
    expect(returned_db).toBeDefined();
    expect(config.graph_database_name).toBeDefined();
    expect(returned_db.databaseName).toBe(config.graph_database_name)
  }, 10000)
  test('mongo.GetInstance(password) rejects on invalid password', async () => {
    console.log("closing connection in test test mongo.GetInstance(password) rejects on invalid password")
    const uri = mongoClient.buildURI(config.mongo_username, 'invalidpassword', config.mongo_endpoint, 'DEFAULT')
    console.log("uri: ", uri)
    const broken_client = new MongoClient(uri)
    /*
    // not sure if i need this - matching the error message is probably enough
    const err_desc: ErrorDescription = {
      message: 'bad auth : authentication failed',
      errmsg: 'bad auth : authentication failed',
      errorLabels:[ 'HandshakeError','ResetPool'],
    }
    await expect(mongo.GetInstance('invalidpassword')).rejects.toThrowError(new MongoServerError(err_desc)) //.toContain('authentication failed')
    */
    await expect(mongo.getMongoDbFromClient(broken_client, config.graph_database_name)).rejects.toThrowError('bad auth : authentication failed')

  }, 10000)
})