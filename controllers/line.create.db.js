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
// const logger = require('../utils/logger')
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
  const line_segment = line['points'].map((point, index, points) => {
    if (index < points.length - 1) {
      const edge = {
        'id': `${line['lineName']}-${line['branchId']}-${point['id']}-${points[index + 1]['id']}`,
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
  // drop the last element if we didnt create an edge for it
  // check if the last element is undefined
  if (line_segment[line_segment.length - 1] === undefined) {
    // drop the last element
    line_segment.pop()
  }

  return line_segment
}


async function get_lines_for_modes(modes) {
  const raw_lines = await tfl_api.get_lines_for_mode(modes)
  const lines = raw_lines.data.map(l => l.id)
  return lines
}


async function get_stoppoints_and_joining_lines(tfl_lines) {
  const { line_segments, stoppoints } = await get_stoppoints(tfl_lines)
  const all_line_edges = line_segments.map(l => generate_single_line(l)).flat()
  console.log(`all_line_edges: ${all_line_edges.length}`)
  return { stoppoints, all_line_edges }
}

async function get_stoppoints(tfl_lines) {
  // get the stoppoints for each line
  // an array of objects, one for each line
  // the object has a .data property which contains the array of stoppoints for this line segment
  // the stoppoints are in order
  const raw_stoppoints = await Promise.all(tfl_lines.map(l => tfl_api.get_line_stoppoints_in_order(l)))

  // extract the .data property from each object
  // this is an array of arrays of stoppoints
  const line_segments = raw_stoppoints.map(stoppoint => stoppoint.data.flat()).flat()
  // we then generate the metadata for each stoppoint
  // and flatten the array to an array of stoppoints
  const flat_stoppoints_with_duplicates = line_segments.map(stoppoint => generate_stoppoints(stoppoint)).flat()
  // we get duplicate stoppoints. Why? we have 472 stoppoints, but get 1353 in the array
  // remove the duplicates by ID
  const stoppoints = flat_stoppoints_with_duplicates.filter((stoppoint, index, self) => {
    return index === self.findIndex((s) => (
      s.id === stoppoint.id
    ))
  })
  console.log(`stoppoints: ${stoppoints.length}, (with duplicates: ${flat_stoppoints_with_duplicates.length}))`)
  return { line_segments, stoppoints }
}

async function store_stoppoints_then_join_them(stoppoints, all_line_edges) {
  const time_between_batches = 0 // ms
  const batch_size = 100
  const stoppoint_success = await chunk_and_send_to_graphdb(stoppoints, graphdb.add_stoppoint, batch_size, time_between_batches)
  const line_success = await chunk_and_send_to_graphdb(all_line_edges, graphdb.add_line, batch_size, time_between_batches)
  console.log(`stoppoint success: ${stoppoint_success}/${stoppoints.length}`)
  console.log(`line success: ${line_success}/${all_line_edges.length}`)
}
/*
function getAllIndexes(arr, val) {
  var indexes = [], i = -1;
  while ((i = arr.indexOf(val, i + 1)) != -1) {
    indexes.push(i);
  }
  return indexes;
}
*/

async function chunk_and_send_to_graphdb(items, send_function, batch_size, time_between_batches) {
  let success_count = 0
  let total_count = 0
  const chunks = chunkArray(items, batch_size)
  for (const chunk of chunks) {
    const result = await Promise.all(chunk.map(sp => send_function(sp)))
    // count how many times the function was successful
    // this is when the promise resolves to contain 'success: true'
    // sometimes, result is empty - remove these first

    // create a const success_this_batch where r.success is defined and r.success is true
    if ((typeof result !== 'undefined') && Array.isArray(result)) {
      const success_this_batch = result.filter(r => Object.prototype.hasOwnProperty.call(r, 'success') && r.success === true).length
      // const success_this_batch = result.filter(r => { r.success).length
      success_count += success_this_batch
      total_count += chunk.length
      console.log(`successes for this batch for ${send_function.name}, ${success_this_batch}/${chunk.length}`, `total successes: ${success_count}/${total_count}`)
      report_errors(success_this_batch, chunk, result)
    }
    else
    {
      console.log('result is undefined or not an array')
    }
  }

  await new Promise(resolve => setTimeout(resolve, time_between_batches))

  return success_count
}


function report_errors(success_this_batch, chunk, result) {
  if (success_this_batch < chunk.length) {
    console.log('some items failed to be added to the graph')
    // get the index of the failed items from result where result.success is false
    const failed_items = result.reduce((a, e, i) => {
      if (!e.success)
        a.push(i)
      return a
    }, [])
    // filter the chunk to get the failed items
    // console.log('failed items:', chunk.filter((_, i) => failed_items.includes(i)))
  }

}

function chunkArray(array, chunkSize) {
  return Array.from(
    { length: Math.ceil(array.length / chunkSize) },
    (_, index) => array.slice(index * chunkSize, (index + 1) * chunkSize)
  )
}

async function go() {
  const tfl_lines = await get_lines_for_modes(modes)
  const { stoppoints, all_line_edges } = await get_stoppoints_and_joining_lines(tfl_lines)
  await store_stoppoints_then_join_them(stoppoints, all_line_edges)
  await graphdb.close()
}

go().then(console.log('done'))