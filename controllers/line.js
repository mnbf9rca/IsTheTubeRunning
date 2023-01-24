const tfl_api = require('../services/tfl_api')
const logger = require('../utils/logger')
const validate_json = require('jsonschema')

var fs = require('fs')
const path = require('node:path')


function load_file(filename) {
  try {
    return JSON.parse(fs.readFileSync(path.resolve(__dirname, 'schemas', filename), 'utf8'))
  } catch (err) {
    console.error(err)
    throw err
  }

}

const simpified_tfl_route_sequence = load_file('simplified_tfl_route_squence.json')

async function get_lines_for_modes(modes) {
  /**
   * fetches lines from tfl for given modes
   * returns a list of lines and some metadata
   *
   * @param {Array} modes - list of modes to fetch lines for
   * @returns {Object} - lines.data - array of lines, lines.ttl - ttl of the data
   *
   **/

  const lines = await tfl_api.get_lines_for_mode(modes)
  return lines
}

async function stoppoints(line, ordered = false) {
  /**
   * Fetches the stoppoints data from TFL by line
   *
   * @param {String} line - line to fetch stoppoints for
   * @returns {Promise} - stoppoints.data - array of stoppoints, stoppoints.ttl - ttl of the data
   *
   **/
  console.log('stoppoints', line, ordered)
  const stoppoints = ordered ? tfl_api.get_line_stoppoints_in_order(line) : tfl_api.get_line_stoppoints(line)
  return stoppoints

}


function generate_single_line_from_branch(branch) {
  /**
   * generates metadata for a single line (edge).
   * A line is an object with the following metadata:
   * id, lineName, branchId direction
   * and an array of points with the following metadata:
   * id, name, naptanId, stationNaptan, lat, lon, lines
   *
   * @param {Object} line - line to store
   * @returns {array} - edges from point to point
   *
   * **/


  // need to add the line to the graph
  // the point[n] and point[n+1] are connected by an edge
  // the edge has the following metadata:
  // id, type, lineName, branchId, direction, from, to
  // the edge is stored in the graph
  // an array of edges is returned
  validate_json.validate(branch, simpified_tfl_route_sequence, { throwError: true })

  const l = branch['points'].map((point, index, points) => {
    if (index < points.length - 1) {
      const edge = {
        'id': `${branch['lineName']}-${branch['branchId']}-${point['id']}-${points[index + 1]['id']}`.replaceAll(' ', '-'),
        'type': 'Line',
        'lineName': branch['lineName'],
        'branchId': branch['branchId'],
        'direction': branch['direction'],
        'from': point['id'],
        'to': points[index + 1]['id']
      }
      return edge
    }
  })
  // for some reason we have an undefined object at the end...
  return l.slice(0, -1)
}

function generate_stoppoints_from_branch(branch) {
  /**
   * generates metadata for each stoppoint in an array
   * A stoppoint is an object with the following metadata:
   * id, name, naptanId, lat, lon, [lines], [modes]
   */
  validate_json.validate(branch, simpified_tfl_route_sequence, { throwError: true })
  return branch.points.map(sp => {
    return {
      'id': sp['id'],
      'name': sp['name'],
      'naptanId': sp['naptanId'],
      'lat': sp['lat'],
      'lon': sp['lon'],
      'modes': sp['modes'],
      'lines': sp['lines'],
      'type': 'StopPoint'
    }
  })
}

module.exports = {
  stoppoints,
  get_lines_for_modes,
  generate_stoppoints_from_branch,
  generate_single_line_from_branch
}