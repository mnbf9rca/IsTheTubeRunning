let originalMongoClientModule = jest.requireActual('../mongo.client')
import { MongoMemoryServer } from 'mongodb-memory-server'

console.log('mocking mongo.client')
let mongoServer: MongoMemoryServer;


const mockGetURI = async (username: string,
  password: string,
  mongo_endpoint: string,
  authMechanism: string = "DEFAULT") => {
  // we use this so that we can mock the response and use mongodb-memory-server
  console.debug("starting MongoMemoryServer")
  mongoServer = await MongoMemoryServer.create();
  console.log("MongoMemoryServer running at: ", mongoServer.getUri())
  return mongoServer.getUri()
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