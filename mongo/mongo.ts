
import { MongoClient, Db , Document} from 'mongodb';
import config from '../utils/config'


import * as mongoclient from './mongo.client';
import * as NetworkTypes from '../network/NetworkTypes';


export function getGraphClient() {
  return mongoclient.GetInstance()
} 

export async function connectGraphClient(client: Db): Promise<void> {
  try {
    const returnedDoc = await client.command({ ping: 1 })
    console.log(returnedDoc)
  } catch (error) {
    throw error
  }
}
