/**
 * This file contains mock responses from the graph.execute module
 * As the responses are quite large, they are stored in a ./graph_execute_responses folder
 * and loaded into this file
 *
 */

const fs = require('fs')
const helpers = require('../../utils/helpers')
const path = require('node:path')



const load_file = (filename) => {
  return fs.readFileSync(path.resolve(__dirname, 'graph_execute_responses', filename), 'utf8')
}

const get_data = (filename) => {
  return helpers.jsonParser(load_file(filename))
}

const add_line_segment= get_data('add_line_segment.json')
const add_stoppoint_simple = get_data('add_stoppoint_simple.json')


module.exports = {
  add_line_segment,
  add_stoppoint_simple
}