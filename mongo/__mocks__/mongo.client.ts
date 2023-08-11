let originalMongoClientModule = jest.requireActual('../mongo.client')
import { MongoMemoryServer, MongoMemoryReplSet } from 'mongodb-memory-server'
import { MongoClient } from 'mongodb';

console.log('mocking mongo.client')
let mongoServer: MongoMemoryServer | MongoMemoryReplSet;

const mockGetURI = async (username: string,
  password: string,
  mongo_endpoint: string,
  authMechanism: string = "DEFAULT") => {
  // we use this so that we can mock the response and use mongodb-memory-server
  if (mongoServer) {
    console.debug("MongoMemoryServer already running")
    return mongoServer.getUri()
  }
  console.debug("starting MongoMemoryServer")
  // mongoServer = await MongoMemoryServer.create();
  mongoServer = await MongoMemoryReplSet.create({ replSet: { count: 3 } }); // This will create an ReplSet with 3 members
  const uri = mongoServer.getUri()
  // check it's running properly
  const con = await MongoClient.connect(uri, {});
  // await while all SECONDARIES will be ready
  await new Promise((resolve) => setTimeout(resolve, 2000));

  const db = await con.db('admin');
  const admin = db.admin();
  const status = await admin.replSetGetStatus();
  const primaries = status.members.filter((m: any) => m.stateStr === 'PRIMARY')
  const secondaries = status.members.filter((m: any) => m.stateStr === 'SECONDARY')

  console.log(`MongoMemoryServer with status at ${uri} with ${primaries.length} primaries and ${secondaries.length} secondaries`)
  return uri
  // return `mongodb+srv://${username}:${password}@${mongo_endpoint}/?retryWrites=true&w=majority&authMechanism=${authMechanism}`
}

const  mockClose = async () => {
  console.debug("stopping MongoMemoryServer")
  return mongoServer.stop()
}

const mocked_module = {
  ...originalMongoClientModule,
  getURI: mockGetURI,
  close: mockClose
}

console.log('mocked module mongo.client')
module.exports = mocked_module