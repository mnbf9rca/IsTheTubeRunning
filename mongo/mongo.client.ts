
import { MongoClient, Db, MongoServerError } from 'mongodb';
import config from '../utils/config'

const mongo_endpoint = config.mongo_endpoint// "mongodb+srv://<username>:<password>@cluster0.yih6sor.mongodb.net/?retryWrites=true&w=majority";
const username = encodeURIComponent(config.mongo_username)
const password = encodeURIComponent(config.mongo_password)
const dbname = config.graph_database_name
const authMechanism = "DEFAULT";

let client: MongoClient;
let cachedDb: Db | null = null
//https://www.mongodb.com/community/forums/t/mongo-isconnected-alternative-for-node-driver-v-4/117041/6



export async function GetInstance(overwrite_password?: string): Promise<Db> {
  const used_password = overwrite_password ? encodeURIComponent(overwrite_password) : password
  const uri =
    `mongodb+srv://${username}:${used_password}@${mongo_endpoint}/?retryWrites=true&w=majority&authMechanism=${authMechanism}`;
  if (cachedDb) {
    console.log("Existing cached connection found!");
    return Promise.resolve(cachedDb);
  }
  console.log("Aquiring new DB connection....");
  try {
    // Connect to our MongoDB database hosted on MongoDB Atlas

    client = new MongoClient(uri, { tls: true })
    await client.connect();
    // Specify which database we want to use
    const db = await client.db(dbname);

    cachedDb = db;
    return Promise.resolve(cachedDb);
  } catch (error) {
    console.log("ERROR aquiring DB Connection!");
    console.log(typeof error)
    console.log(error);
    return Promise.reject(error);
  }
};

export async function close() {
  console.log("Closing DB connection....")
  if (client) {
    console.log("... requesting client to close")
    await client.close()
    console.log("... client close resolved")
  }
  console.log("... releasing cachedDb")
  cachedDb = null;
  return Promise.resolve()
}

