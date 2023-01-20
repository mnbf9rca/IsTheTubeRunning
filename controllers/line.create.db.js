// Description: this script takes an array of `mode`s
// and then calls the API to get the list of lines for each mode
// and then calls the API to get the list of stoppoints for each line in order
// finally, it pushes the stoppoints to the graph
//
// Usage: node controllers/line.update.js
//
// Note: this script is not used in the application, it is just a utility script
// to create the initial graph for the application. Note that it does not take
// account updates to the graph, it just creates the initial graph.


const tfl_api = require('../services/tfl_api')
const logger = require('../utils/logger')
const graphdb = require('../services/graphdb')

const modes = ['tube', 'overground', 'dlr', 'elizabeth-line']


function generate_stoppoints(stoppoints) {
  /**
   * generates metadata for each stoppoint in an array
   * A stoppoint is an object with the following metadata:
   * id, name, naptanId, lat, lon, [lines], [modes]
   */
  return stoppoints.points.map(sp => {
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



function generate_single_line(line) {
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
  const l= line['points'].map((point, index, points) => {
    if (index < points.length - 1) {
      const edge = {
        'id': `${line['lineName']}-${line['branchId']}-${point['id']}-${points[index + 1]['id']}`.replaceAll(' ', '-'),
        'type': 'Line',
        'lineName': line['lineName'],
        'branchId': line['branchId'],
        'direction': line['direction'],
        'from': point['id'],
        'to': points[index + 1]['id']
      }
      return edge
    }
  })
  // for some reason we have an undefined object at the end...
  return l.slice(0,-1)
}


async function get_lines_for_modes(modes) {
  const raw_lines = await tfl_api.get_lines_for_mode(modes)
  const lines = raw_lines.data.map(l => l.id)
  return lines
}


async function get_stoppoints_and_joining_lines(tfl_lines) {
  const raw_stoppoints = await Promise.all(tfl_lines.map(l => tfl_api.get_line_stoppoints_in_order(l)))
  const stoppoints_flat = raw_stoppoints.map(sp => sp.data.flat()).flat()
  // TODO: we get nulls in the lines array. Why?
  // TODO: we get duplicate stoppoints. Why? we have 472 stoppoints, but get 1353 in the array
  const stoppoints = stoppoints_flat.map(sp => generate_stoppoints(sp))
  const lines = stoppoints_flat.map(l => generate_single_line(l))
  return { stoppoints: stoppoints.flat(), lines: lines.flat() }
}

async function store_stoppoints_then_join_them(stoppoints, lines) {
  const time_between_batches = 1000 // ms
  const batch_size = 5
  const stoppoint_success = await chunk_and_send_to_graphdb(stoppoints, graphdb.add_stoppoint, batch_size, time_between_batches)
  console.log(`final stoppoint success: ${stoppoint_success}/${stoppoints.length}`)
  const line_success = await chunk_and_send_to_graphdb(lines, graphdb.add_line, batch_size, time_between_batches)
  console.log(`final line success: ${line_success}/${lines.length}`)
}

async function chunk_and_send_to_graphdb(items, send_function, batch_size, time_between_batches) {
  let success_count = 0
  let total_count = 0
  const chunks = chunkArray(items, batch_size)
  for (const chunk of chunks) {
    const result = await Promise.all(chunk.map(sp => send_function(sp)))
    // count how many times the function was successful
    // this is when the promise resolves to contain 'success: true'
    const success_this_batch = result.filter(r => r.success).length
    success_count += success_this_batch
    total_count += chunk.length
    console.log('successes for this batch for',send_function, `${success_this_batch}/${chunk.length}, total successes: ${success_count}/${total_count}, total items: ${items.length}`)
    if (success_this_batch < chunk.length) {
      console.error('some items failed to be added to the graph')
      // get the index of the failed items from result where result.success is false
      const failed_items = result.reduce((failed_item_indexes, item, index) => {
        if (!item.success){failed_item_indexes.push(index)}
        return failed_item_indexes
      }, [])
      // filter the chunk to get the failed items
      console.error('failed items:', chunk.filter((_, i) => failed_items.includes(i)))
    }
    
    await new Promise(resolve => setTimeout(resolve, time_between_batches))
  }
  return success_count
}


function chunkArray(array, chunkSize) {
  return Array.from(
    { length: Math.ceil(array.length / chunkSize) },
    (_, index) => array.slice(index * chunkSize, (index + 1) * chunkSize)
  );
}

async function go() {
  const tfl_lines = await get_lines_for_modes(modes)
  const { stoppoints, lines } = await get_stoppoints_and_joining_lines(tfl_lines)
  await store_stoppoints_then_join_them(stoppoints, lines)
}

go().then(console.log('done'))