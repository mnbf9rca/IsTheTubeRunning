const tfl_api = require('../services/tfl_api')
const logger = require('../utils/logger')
const validate_json = require('jsonschema')

var fs = require('fs')
const path = require('node:path')


function load_schema(filename) {
  try {
    return fs.readFileSync(path.resolve(__dirname, 'schemas', filename), 'utf8')
  } catch (err) {
    console.error(err)
    throw err
  }

}

const journey_schema = JSON.parse(load_schema('journey.json'))

// a journey is a start point and end point.
// a journey has 1 or more journey segments.
// A journey segment is a start and end point on a single line. The start point and end point must be different.
// A journey belongs to a user.
// A journey has a start time and end time.
// A journey has one or more days of the week.
// A journey has a start date and end date (optional)




module.exports = {

}