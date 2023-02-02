console.log('mocking graph.execute_query')

let originalModule = jest.requireActual('../graphdb.execute')
const mockdata = require('./graphdb.execute.responses')

const mockquery = async function (client, query, maxAttempts, params = null) {
  console.log('mocking graph.execute_query', query, params)
  // look up the query in the mock data
  // if it exists, return the mock data
  // otherwise throw an error
  //let r = await originalModule.execute_query(client,query,maxAttempts,params)

  // iterate through the keys in mockdata. If they match, use the return value

  for (const [key, value] of Object.entries(mockdata)) {
    if (query.match(value.query_regex)) {
      console.log(`matched value ${key}`)
      return Promise.resolve({ data: value.response, success: true })
    }
  }
  throw new Error('query not found in mock data', query)




}

const mocked_module = {
  ...originalModule,
  execute_query: mockquery
}

console.log('mock built')
module.exports = mocked_module