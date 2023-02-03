// file is excluded from coverage because it is only run once to create the initial graph
// and is not used in the application

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


const logger = require('../utils/logger')
const graphdb = require('../services/graphdb')
const line = require('./line')

const modes = ['tube', 'overground', 'dlr', 'elizabeth-line']

async function get_stoppoints_and_joining_lines(tfl_lines_required) {
  const raw_tfl_ordered_lines = await Promise.all(tfl_lines_required.map(l => line.stoppoints(l, true)))
  const tfl_branch_segments = raw_tfl_ordered_lines.map(sp => sp.data).flat()
  const stoppoints = tfl_branch_segments.map(branch => line.generate_stoppoints_from_branch(branch))
  const lines = tfl_branch_segments.map(branch => line.generate_single_line_from_branch(branch))
  return { stoppoints: stoppoints.flat(), lines: lines.flat() }
}

async function store_stoppoints_then_join_them(stoppoints, lines) {
  const time_between_batches = 1000 // ms
  const batch_size = 5
  const stoppoint_success = await chunk_and_send_to_graphdb(stoppoints, graphdb.add_stoppoint, batch_size, time_between_batches)
  console.log(`final stoppoint success: ${stoppoint_success}/${stoppoints.length}`)
  const line_success = await chunk_and_send_to_graphdb(lines, graphdb.add_line_segment, batch_size, time_between_batches)
  console.log(`final line success: ${line_success}/${lines.length}`)
}

async function chunk_and_send_to_graphdb(items, send_function, batch_size, time_between_batches) {
  let success_count = 0
  let total_count = 0
  const chunks = chunk_array(items, batch_size)
  for (const chunk of chunks) {
    const result = await Promise.all(chunk.map(sp => send_function(sp)))
    // count how many times the function was successful
    // this is when the promise resolves to contain 'success: true'
    const success_this_batch = result.filter(r => r.success).length
    success_count += success_this_batch
    total_count += chunk.length
    console.log('successes for this batch for', send_function, `${success_this_batch}/${chunk.length}, total successes: ${success_count}/${total_count}, total items: ${items.length}`)
    if (success_this_batch < chunk.length) {
      console.error('some items failed to be added to the graph')
      // get the index of the failed items from result where result.success is false
      const failed_items = result.reduce((failed_item_indexes, item, index) => {
        if (!item.success) { failed_item_indexes.push(index) }
        return failed_item_indexes
      }, [])
      // filter the chunk to get the failed items
      console.error('failed items:', chunk.filter((_, i) => failed_items.includes(i)))
    }
    await new Promise(resolve => setTimeout(resolve, time_between_batches))
  }
  return success_count
}


function chunk_array(array, chunkSize) {
  return Array.from(
    { length: Math.ceil(array.length / chunkSize) },
    (_, index) => array.slice(index * chunkSize, (index + 1) * chunkSize)
  )
}

async function go() {
  const tfl_lines = await line.get_lines_for_modes(modes)
  const line_ids = tfl_lines.data.map(l => l.id)
  const { stoppoints, lines } = await get_stoppoints_and_joining_lines(line_ids)
  await store_stoppoints_then_join_them(stoppoints, lines)
}

go().then(console.log('done'))