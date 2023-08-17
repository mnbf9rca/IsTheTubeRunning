import { describe, expect, test } from '@jest/globals'
import { MongoClient, ObjectId } from 'mongodb';

//import { MongoServerError, ErrorDescription } from 'mongodb'
import * as mongo from '../mongo';
import * as mongoClient from '../mongo.client';
import config = require('../../utils/config');
import * as GraphTypes from '../GraphTypesZodManual';
import * as z from "zod";

type edgeWithObjectIdsSchemaType = z.infer<typeof GraphTypes.edgeWithObjectIdsSchema>


const invalidObjectId = (propertyName: string): z.ZodIssue => {
  return {
    code: z.ZodIssueCode.custom,
    message: 'Invalid ObjectId',
    fatal: true,
    path: [
      propertyName
    ]
  }
}
const missingString = (propertyName: string): z.ZodIssue => {
  return {
    code: z.ZodIssueCode.invalid_type,
    expected: 'string',
    received: 'undefined',
    path: [
      propertyName
    ],
    message: 'Required'
  }
}
const isObjectExpectString = (propertyName: string): z.ZodIssue => {
  return {
    code: z.ZodIssueCode.invalid_type,
    expected: 'string',
    received: 'object',
    path: [
      propertyName
    ],
    message: 'Expected string, received object'
  }
}

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
describe('test insertNewEdge', () => {
  test('rejects when including _id property in edge', async () => {
    const mongo_client = await mongo.getMongoClient();
    const db = await mongo.getMongoDbFromClient(mongo_client, config.graph_database_name);
    const session = mongo_client.startSession()
    const edge: edgeWithObjectIdsSchemaType = {
      from: new ObjectId('thisisthefro'),
      to: new ObjectId('thisistheto!'),
      _id: "arbitrary id"
    }

    await expect(mongoClient.insertNewEdge(edge, db, session)).rejects.toThrowError('The edge object should not contain an ._id property')
  })
  test('rejects with missing .from property', async () => {
    const mongo_client = await mongo.getMongoClient();
    const db = await mongo.getMongoDbFromClient(mongo_client, config.graph_database_name);
    const session = mongo_client.startSession()
    const edge = { to: new ObjectId('thisistheto!') }


    const expected_issue: z.ZodIssue[] = [
      {
        code: z.ZodIssueCode.invalid_union,
        unionErrors: [
          new z.ZodError([invalidObjectId('to')]),
          new z.ZodError([missingString('from'), isObjectExpectString('to')])
        ],
        path: [],
        message: 'Invalid input'
      }
    ]

    const expected_error = 'The edge object should contain a .from and .to property that are ObjectIds'
    //const expected_error = new z.ZodError(expected_issue)

    // coerce type
    await expect(mongoClient
      .insertNewEdge(
        edge as unknown as z.infer<typeof GraphTypes.edgeWithObjectIdsSchema>,
        db,
        session))
      .rejects
      .toThrow(expected_error)

  })
  test('rejects with missing .to property', async () => {
    const mongo_client = await mongo.getMongoClient();
    const db = await mongo.getMongoDbFromClient(mongo_client, config.graph_database_name);
    const session = mongo_client.startSession()
    const edge = { from: new ObjectId('thisisthefro') }

    const expected_error = 'The edge object should contain a .from and .to property that are ObjectIds'

    // coerce type
    await expect(mongoClient
      .insertNewEdge(
        edge as unknown as z.infer<typeof GraphTypes.edgeWithObjectIdsSchema>,
        db,
        session))
      .rejects
      .toThrow(expected_error)

  })
  test('rejects with missing .from and .to properties', async () => {
    const mongo_client = await mongo.getMongoClient();
    const db = await mongo.getMongoDbFromClient(mongo_client, config.graph_database_name);
    const session = mongo_client.startSession()
    const edge = {}

    const expected_error = 'The edge object should contain a .from and .to property that are ObjectIds'
    // coerce type
    await expect(mongoClient
      .insertNewEdge(
        edge as unknown as z.infer<typeof GraphTypes.edgeWithObjectIdsSchema>,
        db,
        session))
      .rejects
      .toThrow(expected_error)

  })
  test('rejects when from is not instance of ObjectId', async () => {
    const mongo_client = await mongo.getMongoClient();
    const db = await mongo.getMongoDbFromClient(mongo_client, config.graph_database_name);
    const session = mongo_client.startSession()
    const edge = { from: 'from', to: new ObjectId('thisistheto!') }
    const expected_error = 'The edge object should contain a .from and .to property that are ObjectIds'

    // coerce type
    await expect(mongoClient
      .insertNewEdge(
        edge as unknown as z.infer<typeof GraphTypes.edgeWithObjectIdsSchema>,
        db,
        session))
      .rejects
      .toThrowError(expected_error)
  })
  test('rejects when to is not instance of ObjectId', async () => {
    const mongo_client = await mongo.getMongoClient();
    const db = await mongo.getMongoDbFromClient(mongo_client, config.graph_database_name);
    const session = mongo_client.startSession()
    const edge = { to: 'to', from: new ObjectId('thisistheto!') }
    const expected_error = 'The edge object should contain a .from and .to property that are ObjectIds'

    // coerce type
    await expect(mongoClient
      .insertNewEdge(
        edge as unknown as z.infer<typeof GraphTypes.edgeWithObjectIdsSchema>,
        db,
        session))
      .rejects
      .toThrowError(expected_error)
  })
  test('rejects when properties include a function', async () => {
    const mongo_client = await mongo.getMongoClient();
    const db = await mongo.getMongoDbFromClient(mongo_client, config.graph_database_name);
    const session = mongo_client.startSession()
    const edge = {
      from: new ObjectId('thisisthefro'),
      to: new ObjectId('thisistheto!'),
      erritem: () => { } // functions are not valid JSON
    }

    const expected_error = "Invalid JSON value" // somewhere...

    // coerce type
    await expect(mongoClient
      .insertNewEdge(
        edge as unknown as z.infer<typeof GraphTypes.edgeWithObjectIdsSchema>,
        db,
        session))
      .rejects
      .toThrowError(expected_error)
  })
  test('rejects when properties include a nonserializable object', async () => {
    const mongo_client = await mongo.getMongoClient();
    const db = await mongo.getMongoDbFromClient(mongo_client, config.graph_database_name);
    const session = mongo_client.startSession()
    const edge = {
      from: new ObjectId('thisisthefro'),
      to: new ObjectId('thisistheto!'),
      erritem: mongo_client
    }

    const expected_error = "Invalid JSON value" // somewhere...

    // coerce type
    await expect(mongoClient
      .insertNewEdge(
        edge as unknown as z.infer<typeof GraphTypes.edgeWithObjectIdsSchema>,
        db,
        session))
      .rejects
      .toThrowError(expected_error)
  })
  test('inserts a valid simple object', async () => {
    const mongo_client = await mongo.getMongoClient();
    const db = await mongo.getMongoDbFromClient(mongo_client, config.graph_database_name);
    const session = mongo_client.startSession()
    const edge = {
      from: new ObjectId('thisisthefro'),
      to: new ObjectId('thisistheto!')
    }

    const result = await mongoClient
      .insertNewEdge(
        edge,
        db,
        session)
    expect(result.acknowledged).toBeTruthy()
    expect(result.insertedId).toBeDefined()
    expect(result.insertedId).toBeInstanceOf(ObjectId)
  })
  test('inserts a valid object with other properties', async () => {
    const mongo_client = await mongo.getMongoClient();
    const db = await mongo.getMongoDbFromClient(mongo_client, config.graph_database_name);
    const session = mongo_client.startSession()
    const edge = {
      from: new ObjectId('thisisthefro'),
      to: new ObjectId('thisistheto!'),
      stringProp: 'string',
      numberProp: 1,
      booleanProp: true,
      nullProp: null,
      objectProp: { key: 'value' },
      arrayProp: ['value1', 'value2']
    }

    const result = await mongoClient
      .insertNewEdge(
        edge,
        db,
        session)
    expect(result.acknowledged).toBeTruthy()
    expect(result.insertedId).toBeDefined()
    expect(result.insertedId).toBeInstanceOf(ObjectId)
  })
})