const { describe, expect, test } = require('@jest/globals')

const graph = require('../graphdb')
jest.mock('../graphdb.execute')

const mockdata = require('../__mocks__/graphdb.execute.responses')


const randomString = () => Math.random().toString(36).slice(2, 7)



const generate_random_stoppoint = (number_of_modes, number_of_lines) => {
  const new_object_id = randomString()
  const [lat, lon] = generate_random_lat_lon()
  const stoppoint = {
    type: 'stoppoint',
    id: new_object_id,
    name: randomString(),
    naptanId: new_object_id,
    lat: lat.toString(),
    lon: lon.toString(),
    modes: generate_random_array(number_of_modes),
    lines: generate_random_array(number_of_lines)
  }
  return stoppoint
}

describe('test add_line', () => {
  // const spy = jest.spyOn(require('../graphdb.execute').primitive, 'execute_query')
  jest.setTimeout(6000)
  
  test('test adding a line', async () => {
    const input_data = mockdata.add_line.input
    const expected_result = mockdata.add_line.expected
    const actual_result = await graph.add_line(input_data, false)
    
    expect(actual_result).toMatchObject(expected_result)
  })
})


const generate_line = (first_stoppoint, second_stoppoint) => {
  /*
    const add_query = `addE('TO')
                    .from(g.V('${line_edge['from']}'))
                    .to(g.V('${line_edge['to']}'))
                    .property('id', '${line_edge['id']}')
                    .property('line', '${line_edge['lineName']}')
                    .property('branch', '${line_edge['branchId']}')
                    .property('direction', '${line_edge['direction']}')`
                    */
  const line_name = randomString()
  const branch_number = Math.floor(Math.random() * 11)
  const line_id = `${line_name}-${branch_number}-${first_stoppoint['id']}-${second_stoppoint['id']}`.replaceAll(' ', '-')
  const line = {
    type: 'line',
    id: line_id,
    from: first_stoppoint['id'],
    to: second_stoppoint['id'],
    lineName: line_name,
    branchId: branch_number,
    direction: randomString()
  }
  return line
}

const generate_random_array = (number_of_modes) => {
  // return an array containing number_of_modes randomString()
  const modes = new Array(number_of_modes).fill(null).map(() => randomString())
  return modes
}

const generate_random_lat_lon = () => {
  // generate a random lat and lon that are somewhere roughly inside London
  const lat = Math.random() * (51.5 - 51.0) + 51.0
  const lon = Math.random() * (-0.1 - -0.5) + -0.5
  return [lat, lon]
}