const fs = require('fs')
const helpers = require('../../utils/helpers')
const path = require('node:path')

const load_file = (filename) => {
  return fs.readFileSync(path.resolve(__dirname, 'line_expected_responses', filename), 'utf8')
}

const get_data = (filename) => {
  return helpers.jsonParser(load_file(filename))
}

const line_stoppoints_victoria_true = get_data('line_stoppoints_victoria_true.json') 
const line_stoppoints_victoria_false = get_data('line_stoppoints_victoria_false.json') 
const lines_for_mode_tube_overground = get_data('lines_for_mode_tube_overground.json')
const lines_for_mode_overground = get_data('lines_for_mode_overground.json')
const lines_for_mode_tube = get_data('lines_for_mode_tube.json')
const generate_stoppoints_from_branch_1_expected = get_data('generate_stoppoints_from_branch_1_expected.json')
const generate_line_for_branch_1_expected = get_data('generate_line_for_branch_1_expected.json')
const branch_data_1 = get_data('branch_data_1.json')

module.exports = { line_stoppoints_victoria_true,
  line_stoppoints_victoria_false,
  lines_for_mode_tube_overground,
  lines_for_mode_overground,
  lines_for_mode_tube,
  generate_stoppoints_from_branch_1_expected,
  generate_line_for_branch_1_expected,
  branch_data_1
}