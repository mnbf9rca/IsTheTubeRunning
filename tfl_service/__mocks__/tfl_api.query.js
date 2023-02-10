const responses = require('./tfl_api.query.axios_responses')
console.log('mocking TfL API')

const { check_params } = require('../tests/test_helpers')


let originalModule = jest.requireActual('../tfl_api.query')

const axios = require('axios')
jest.mock('axios')
const mockquery = (url, params) => {
  /**
   * Mocks the query function from tfl_api.query
   */
  console.log('mocking query', url, params)

  switch (url.toLowerCase()) {
  case 'line/victoria/route/sequence/all':
    //TODO add support for crowding
    if (check_params(params, { excludeCrowding: true })) {
      axios.get.mockResolvedValue(responses.get_line_victoria_route_sequence_all_no_crowding)
    } else {
      throw new Error('crowding not supported on mock line/victoria/route/sequence/all')
    }
    return originalModule.query(url, params)

  case 'line/victoria/stoppoints':
    axios.get.mockResolvedValue(responses.get_line_stoppoints_victoria)
    return originalModule.query(url, params)

  case 'line/mode/tube/status':
    if (check_params(params, { detail: true })) {
      axios.get.mockResolvedValue(responses.get_line_mode_tube_status_detail_true_disrupted)
    } else {
      axios.get.mockResolvedValue(responses.get_line_mode_tube_status_detail_false_disrupted)
    }
    return originalModule.query(url, params)

  case 'line/mode/tube,overground/status':
    if (check_params(params, { detail: true })) {
      axios.get.mockResolvedValue(responses.get_line_mode_tube_overground_status_detail_true_disrupted)
    } else {
      axios.get.mockResolvedValue(responses.get_line_mode_tube_overground_status_detail_false_disrupted)
    }
    return originalModule.query(url, params)

  case 'line/mode/tube,overground,dlr/status':
    if (check_params(params, { detail: true })) {
      axios.get.mockResolvedValue(responses.get_line_mode_tube_overground_dlr_status_detail_true_disrupted)
    } else {
      axios.get.mockResolvedValue(responses.get_line_mode_tube_overground_status_detail_false_disrupted)
    }
    return originalModule.query(url, params)
  case 'line/mode/tube/route':
    axios.get.mockResolvedValue(responses.get_line_mode_tube_route)
    return originalModule.query(url, params)

  case 'line/mode/tube,overground/route':
    axios.get.mockResolvedValue(responses.get_line_mode_tube_overground_route)
    return originalModule.query(url, params)

  default:
    throw new Error(`No mock response for ${url}`)

  }
}

const mocked_module = {
  ...originalModule,
  query: mockquery
}




//originalModule['query'] = mockquery
console.log('mocked')

//mockquery;
module.exports = mocked_module