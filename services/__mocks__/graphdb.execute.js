console.log('mocking graph.execute_query')

let originalModule = jest.requireActual('../graphdb.execute')
const mockdata = require('./graphdb.execute.responses')

const mockquery = async function (client, query, maxAttempts, params = null) {
  console.log('mocking graph.execute_query', query, params)
  // look up the query in the mock data
  // if it exists, return the mock data
  // otherwise throw an error
  // let r = await originalModule.execute_query(client,query,maxAttempts,params)

  if (query.match(mockdata.add_line.query_regex)) {
    console.log('matched add_line query')
    return Promise.resolve({ data: mockdata.add_line.response, success: true })
  }
  else {
    throw new Error('query not found in mock data')
  }
  


}

const mocked_module = {
  ...originalModule,
  execute_query: mockquery
}

console.log('mock built')
module.exports = mocked_module