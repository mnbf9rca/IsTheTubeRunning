const logger = require('../utils/logger')
const validate_json = require('jsonschema')
const graphdb = require('../services/graphdb')

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

const user_schema = JSON.parse(load_schema('user.json'))

// a user has a name, email address, password, and 0 or more journeys.
// a user can be 'verified' or 'unverified' depending whether they have verified their email address.
// a user can be 'active' or 'inactive' depending whether they have logged in recently.
// note that we'll remove 'password' later in preference for OAuth or similar.
// users do not have 'admin' levels


function create_user(user) {
  // validate the user object
  validate_json.validate(user, user_schema, { throwError: true })

}

module.exports = {
}