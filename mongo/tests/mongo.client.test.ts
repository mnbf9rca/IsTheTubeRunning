import { describe, expect, test } from '@jest/globals'
import { MongoClient, ObjectId } from 'mongodb';

//import { MongoServerError, ErrorDescription } from 'mongodb'
import * as mongo from '../mongo';
import * as mongoClient from '../mongo.client';
import config = require('../../utils/config');
import * as GraphTypes from '../GraphTypesZodManual';
import * as z from "zod";
import { ValidationError } from 'zod-validation-error';

type jsonWithoutFromOrTo = z.z.infer<typeof GraphTypes.jsonWithoutFromOrTo>

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
    const edge: jsonWithoutFromOrTo = {
      _id: "arbitrary id"
    }
    const from = new ObjectId('thisisthefro')
    const to = new ObjectId('thisistheto!')

    await expect(mongoClient
      .insertNewEdge(
        edge as unknown as jsonWithoutFromOrTo,
        from as unknown as ObjectId,
        to as unknown as ObjectId,
        db,
        session))
      .rejects
      .toThrowError('The edge object should not contain an ._id property')
  })
  test('rejects with missing .from property', async () => {
    const mongo_client = await mongo.getMongoClient();
    const db = await mongo.getMongoDbFromClient(mongo_client, config.graph_database_name);
    const session = mongo_client.startSession()
    const edge = {}
    const to = new ObjectId('thisistheto!')
    const from = undefined

    const expected_error = 'Must provide from and to that are ObjectIds'
    //const expected_error = new z.ZodError(expected_issue)

    // coerce type
    await expect(mongoClient
      .insertNewEdge(
        edge as unknown as jsonWithoutFromOrTo,
        from as unknown as ObjectId,
        to as unknown as ObjectId,
        db,
        session))
      .rejects
      .toThrow(expected_error)

  })
  test('rejects with missing .to property', async () => {
    const mongo_client = await mongo.getMongoClient();
    const db = await mongo.getMongoDbFromClient(mongo_client, config.graph_database_name);
    const session = mongo_client.startSession()
    const edge = {}
    const from = new ObjectId('thisisthefro')
    const to = undefined

    const expected_error = 'Must provide from and to that are ObjectIds'

    // coerce type
    await expect(mongoClient
      .insertNewEdge(
        edge as unknown as jsonWithoutFromOrTo,
        from as unknown as ObjectId,
        to as unknown as ObjectId,
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
    const from = undefined
    const to = undefined

    const expected_error = 'Must provide from and to that are ObjectIds'
    // coerce type
    await expect(mongoClient
      .insertNewEdge(
        edge as unknown as jsonWithoutFromOrTo,
        from as unknown as ObjectId,
        to as unknown as ObjectId,
        db,
        session))
      .rejects
      .toThrow(expected_error)

  })
  test('rejects when from is not instance of ObjectId', async () => {
    const mongo_client = await mongo.getMongoClient();
    const db = await mongo.getMongoDbFromClient(mongo_client, config.graph_database_name);
    const session = mongo_client.startSession()
    const edge = {}
    const from = 'from'
    const to = new ObjectId('thisistheto!')
    const expected_error = 'Must provide from and to that are ObjectIds'

    // coerce type
    await expect(mongoClient
      .insertNewEdge(
        edge as unknown as jsonWithoutFromOrTo,
        from as unknown as ObjectId,
        to as unknown as ObjectId,
        db,
        session))
      .rejects
      .toThrow(expected_error)
  })
  test('rejects when to is not instance of ObjectId', async () => {
    const mongo_client = await mongo.getMongoClient();
    const db = await mongo.getMongoDbFromClient(mongo_client, config.graph_database_name);
    const session = mongo_client.startSession()
    const edge = {}
    const to = 'to'
    const from = new ObjectId('thisisthefro')
    const expected_error = 'Must provide from and to that are ObjectIds'

    // coerce type
    // coerce type
    await expect(mongoClient
      .insertNewEdge(
        edge as unknown as jsonWithoutFromOrTo,
        from as unknown as ObjectId,
        to as unknown as ObjectId,
        db,
        session))
      .rejects
      .toThrow(expected_error)
  })
  test('rejects when properties include a function', async () => {
    const mongo_client = await mongo.getMongoClient();
    const db = await mongo.getMongoDbFromClient(mongo_client, config.graph_database_name);
    const session = mongo_client.startSession()
    const edge = {
      erritem: () => { } // functions are not valid JSON
    }
    const from = new ObjectId('thisisthefro')
    const to = new ObjectId('thisistheto!')

    const expected_error = new ValidationError('Validation error: Invalid JSON value at "erritem"')
    "Invalid JSON value" // somewhere...

    // coerce type
    await expect(mongoClient
      .insertNewEdge(
        edge as unknown as jsonWithoutFromOrTo,
        from as unknown as ObjectId,
        to as unknown as ObjectId,
        db,
        session))
      .rejects
      .toThrow(expected_error)
  })
  test('rejects when edge includes from with ObjectID', async () => {
    const mongo_client = await mongo.getMongoClient();
    const db = await mongo.getMongoDbFromClient(mongo_client, config.graph_database_name);
    const session = mongo_client.startSession()
    const edge = {
      from: new ObjectId('thisisthefr2') // functions are not valid JSON
    }
    const from = new ObjectId('thisisthefro')
    const to = new ObjectId('thisistheto!')

    const expected_error = new ValidationError('Validation error: Expected never, received object at "from"')

    // coerce type
    await expect(mongoClient
      .insertNewEdge(
        edge as unknown as jsonWithoutFromOrTo,
        from as unknown as ObjectId,
        to as unknown as ObjectId,
        db,
        session))
      .rejects
      .toThrow(expected_error)
  })
  test('rejects when edge includes from with string', async () => {
    const mongo_client = await mongo.getMongoClient();
    const db = await mongo.getMongoDbFromClient(mongo_client, config.graph_database_name);
    const session = mongo_client.startSession()
    const edge = {
      from: 'someFrom' // functions are not valid JSON
    }
    const from = new ObjectId('thisisthefro')
    const to = new ObjectId('thisistheto!')

    const expected_error = new ValidationError('Validation error: Expected never, received string at "from"')

    // coerce type
    await expect(mongoClient
      .insertNewEdge(
        edge as unknown as jsonWithoutFromOrTo,
        from as unknown as ObjectId,
        to as unknown as ObjectId,
        db,
        session))
      .rejects
      .toThrow(expected_error)
  })
  test('rejects when properties include a nonserializable object', async () => {
    const mongo_client = await mongo.getMongoClient();
    const db = await mongo.getMongoDbFromClient(mongo_client, config.graph_database_name);
    const session = mongo_client.startSession()
    const edge = {
      erritem: mongo_client
    }
    const from = new ObjectId('thisisthefro')
    const to = new ObjectId('thisistheto!')

    const expected_error = "Invalid JSON value" // somewhere...

    // coerce type
    await expect(mongoClient
      .insertNewEdge(
        edge as unknown as jsonWithoutFromOrTo,
        from as unknown as ObjectId,
        to as unknown as ObjectId,
        db,
        session))
      .rejects
      .toThrow(expected_error)
  })
  test('inserts a valid simple object', async () => {
    const mongo_client = await mongo.getMongoClient();
    const db = await mongo.getMongoDbFromClient(mongo_client, config.graph_database_name);
    const session = mongo_client.startSession()
    const edge = {

    }
    const from = new ObjectId('thisisthefro')
    const to = new ObjectId('thisistheto!')

    const result = await mongoClient
      .insertNewEdge(
        edge as unknown as jsonWithoutFromOrTo,
        from as unknown as ObjectId,
        to as unknown as ObjectId,
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
      stringProp: 'string',
      numberProp: 1,
      booleanProp: true,
      nullProp: null,
      objectProp: { key: 'value' },
      arrayProp: ['value1', 'value2']
    }
    const from = new ObjectId('thisisthefro')
    const to = new ObjectId('thisistheto!')

    const result = await mongoClient
    .insertNewEdge(
      edge as unknown as jsonWithoutFromOrTo,
      from as unknown as ObjectId,
      to as unknown as ObjectId,
      db,
      session)
    expect(result.acknowledged).toBeTruthy()
    expect(result.insertedId).toBeDefined()
    expect(result.insertedId).toBeInstanceOf(ObjectId)
  })
})