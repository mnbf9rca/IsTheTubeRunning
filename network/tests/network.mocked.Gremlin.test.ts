const graph = require('../../graph/graphdb')
jest.mock('../../graph/graphdb.execute')
const validator = require('jsonschema')


const mockdata = require('../../graph/__mocks__/graphdb.execute.responses')

describe.skip('graphdb.execute tests with mocked graph response', () => {
  describe('test add_line_segment', () => {
    test('adding a line', async () => {
      const input_data = mockdata.add_line_segment.input
      const expected_result = mockdata.add_line_segment.expected
      const actual_result = await graph.add_line_segment(input_data, false)
      expect(actual_result).toMatchObject(expected_result)
    })
    test.skip('throws on incorrect schema', async () => {
      // not using jsonschema at the moment
      const v = require('jsonschema')
      const spy = jest.spyOn(v, 'validate')
      const input_data = mockdata.add_stoppoint_simple.input
      await expect(graph.add_line_segment(input_data, false)).rejects.toThrow(validator.ValidatorResultError)
      expect(spy).toHaveBeenCalledTimes(1)
    })
    test.skip('throws on missing key', async () => {
      // not using jsonschema at the moment
      const v = require('jsonschema')
      const spy = jest.spyOn(v, 'validate')
      let input_data = mockdata.add_line_segment.input
      delete input_data.lineName
      await expect(graph.add_line_segment(input_data, false)).rejects.toThrow(validator.ValidatorResultError)
      expect(spy).toHaveBeenCalledTimes(1)
    })
    // TODO: add more tests: test invalid schema, check for upsert
  })
  describe.skip('test deserialize_stoppoint', () => {
    test('returns a properly formed object for a single result', () => {
      const input_value = JSON.parse('[{"id":"28fjp","label":"stoppoint","type":"vertex","properties":{"name":[{"id":"4d89ef30-f815-42a1-8b7b-34b825959db1","value":"yboa6"}],"naptanId":[{"id":"28fjp|naptanId","value":"28fjp"}],"lat":[{"id":"dd1b087f-5b33-4076-9ab6-9262a9f2c17c","value":"51.39571760958728"}],"lon":[{"id":"18b1c07d-76fa-48ec-997e-4eb20c7bf235","value":"-0.14384083030070627"}],"modes":[{"id":"24767fe3-b142-4f29-b059-000c0838c413","value":"31t3i"},{"id":"1bda7368-b2f7-4913-8a94-8906de99a89d","value":"dx038"}],"lines":[{"id":"dadd01de-522c-41cd-b217-7329b8cf524e","value":"dqgm6"},{"id":"d5fdc72f-41ea-4277-a367-d1fc4da22a84","value":"n3nws"},{"id":"465966e9-939f-4bda-a40e-5565e487c50d","value":"2pnpi"}]}}]')
      const expected_result = JSON.parse('[{"id":"28fjp","label":"stoppoint","type":"vertex","lat":"51.39571760958728","lon":"-0.14384083030070627","name":"yboa6","modes":["31t3i","dx038"],"lines":["dqgm6","n3nws","2pnpi"],"naptanId":"28fjp"}]')
      const actual_result = graph.deserialize_stoppoint(input_value)
      expect(actual_result).toMatchObject(expected_result)
    })
    test('returns a properly formed object for a multiple result', () => {
      const input_value = JSON.parse('[{"id":"28fjp","label":"stoppoint","type":"vertex","properties":{"name":[{"id":"4d89ef30-f815-42a1-8b7b-34b825959db1","value":"yboa6"}],"naptanId":[{"id":"28fjp|naptanId","value":"28fjp"}],"lat":[{"id":"dd1b087f-5b33-4076-9ab6-9262a9f2c17c","value":"51.39571760958728"}],"lon":[{"id":"18b1c07d-76fa-48ec-997e-4eb20c7bf235","value":"-0.14384083030070627"}],"modes":[{"id":"24767fe3-b142-4f29-b059-000c0838c413","value":"31t3i"},{"id":"1bda7368-b2f7-4913-8a94-8906de99a89d","value":"dx038"}],"lines":[{"id":"dadd01de-522c-41cd-b217-7329b8cf524e","value":"dqgm6"},{"id":"d5fdc72f-41ea-4277-a367-d1fc4da22a84","value":"n3nws"},{"id":"465966e9-939f-4bda-a40e-5565e487c50d","value":"2pnpi"}]}},{"id":"gylob","label":"stoppoint","type":"vertex","properties":{"name":[{"id":"a1c44656-eb22-4e5d-8aae-33c5f17da296","value":"oh7m3"}],"naptanId":[{"id":"gylob|naptanId","value":"gylob"}],"lat":[{"id":"62051f9a-92ae-47ab-bbb5-06eb9244eb56","value":"51.21501641747709"}],"lon":[{"id":"827bcebb-fbd8-4190-83f4-faac94aec243","value":"-0.17557826765462625"}],"modes":[{"id":"34ffc77f-b10d-4e27-9764-8d0503e53e3d","value":"dzcpd"},{"id":"adba3358-2001-4cf0-bb64-526ed281546b","value":"you2p"}],"lines":[{"id":"6328afef-d6e4-4cd1-8c7e-ea7dfb400879","value":"15nl0"},{"id":"a4599095-c467-458c-9c9b-cb21bd63d44e","value":"9s3dt"},{"id":"ec512682-ffc1-40fd-9255-76917866362b","value":"xtcek"}]}}]')
      const expected_result = JSON.parse('[{"id":"28fjp","label":"stoppoint","type":"vertex","lat":"51.39571760958728","lon":"-0.14384083030070627","name":"yboa6","modes":["31t3i","dx038"],"lines":["dqgm6","n3nws","2pnpi"],"naptanId":"28fjp"},{"id":"gylob","label":"stoppoint","type":"vertex","lat":"51.21501641747709","lon":"-0.17557826765462625","name":"oh7m3","modes":["dzcpd","you2p"],"lines":["15nl0","9s3dt","xtcek"],"naptanId":"gylob"}]')
      const actual_result = graph.deserialize_stoppoint(input_value)
      expect(actual_result).toMatchObject(expected_result)
    })
    test('returns a properly formed object for empty result', () => {
      const input_value: any[] = []
      const expected_result: any[] = []
      const actual_result = graph.deserialize_stoppoint(input_value)
      expect(actual_result).toMatchObject(expected_result)
    })
  })
  describe.skip('test flattenProperties', () => {
    test('array of property values', () => {
      const input_value = JSON.parse('{"value1": [{"id": "id1", "value": "valuea"}], "value2": [{"id": "id2", "value": "valueb"}]}')
      const expected_result = JSON.parse('{"value1": "valuea", "value2": "valueb"}')
      const actual_result = graph.flattenProperties(input_value)
      expect(actual_result).toMatchObject(expected_result)
    })
    test('single property', () => {
      const input_value = JSON.parse('{"value1": [{"id": "id1", "value": "valuea"}]}')
      const expected_result = JSON.parse('{"value1": "valuea"}')
      const actual_result = graph.flattenProperties(input_value)
      expect(actual_result).toMatchObject(expected_result)
    })
    test('empty object', () => {
      const input_value = {}
      const expected_result = {}
      const actual_result = graph.flattenProperties(input_value)
      expect(actual_result).toMatchObject(expected_result)
    })
    test('property is a dict', () => {
      const input_value = JSON.parse('{"value1": "valueA"}')
      const expected_result = JSON.parse('{"value1": "valueA"}')
      const actual_result = graph.flattenProperties(input_value)
      expect(actual_result).toMatchObject(expected_result)
    })
    test('mix of array and dict properties', () => {
      const input_value = JSON.parse('{"value1": [{"id": "id1", "value": "valuea"}], "value2": "valueb"}')
      const expected_result = JSON.parse('{"value1": "valuea", "value2": "valueb"}')
      const actual_result = graph.flattenProperties(input_value)
      expect(actual_result).toMatchObject(expected_result)
    })
    test('propery with array of dicts', () => {
      const input_value = JSON.parse('{"value1": [{"id": "id1", "value": "valuea"}, {"id": "id2", "value": "valueb"}]}')
      const expected_result = JSON.parse('{"value1": ["valuea", "valueb"]}')
      const actual_result = graph.flattenProperties(input_value)
      expect(actual_result).toMatchObject(expected_result)
    })
  }),
  test.skip('add a single stoppoint', async () => {
    jest.setTimeout(20000)
    const new_stoppoint = generate_random_Stoppoint(2, 3)
    // in the return value, the label is the same as the type and the type is the DB object type, vertex
    // TODO here, we need to cast to a new type, Graph_Stoppoint or something
    // as the spread syntax is exposing all of the private properties
    const expected_result = { ...(new_stoppoint.getObject()), 'lat': String(new_stoppoint.lat), 'lon': String(new_stoppoint.lon), 'label': new_stoppoint['type'], 'type': 'vertex' }
    const id = new_stoppoint['id']
    list_of_added_vertices.push(id)
    const actual_result = await GraphDB.add_stoppoint(new_stoppoint, true)
    if (!actual_result['success']) {
      console.error('error result:', actual_result)
    }
    expect(actual_result['success']).toBe(true)
    expect(actual_result['data']).toHaveLength(1)
    expect(actual_result['data'][0]).toEqual(expected_result)

  })
  test.skip('find the route between our two known stoppoints', async () => {
    jest.setTimeout(20000)
    const expected_result = {
      data: [[{
        id: known_graph.first.id,
        label: 'stoppoint',
        type: 'vertex',
        name: known_graph.first.name,
        naptanId: known_graph.first.id,
        lat: String(known_graph.first.lat),
        lon: String(known_graph.first.lon),
        modes: known_graph.first.modes,
        lines: known_graph.first.lines
      },
      {
        id: known_graph.line.id,
        from: known_graph.line.from!.id,
        to: known_graph.line.to!.id,
        line: known_graph.line.lineName,
        branch: known_graph.line.branchId.toString(),
        direction: known_graph.line.direction,
      },
      {
        id: known_graph.second.id,
        label: 'stoppoint',
        type: 'vertex',
        name: known_graph.second.name,
        naptanId: known_graph.second.id,
        lat: String(known_graph.second.lat),
        lon: String(known_graph.second.lon),
        modes: known_graph.second.modes,
        lines: known_graph.second.lines
      }]],
      success: true,
      status_code: null
    }
    const actual_result = await graph.find_route_between_stops(known_graph.first['id'], known_graph.second['id'], known_graph.line.lineName)
    expect(actual_result).toMatchObject(expected_result)
  })
  describe('test add_stoppoint', () => {
    test('adding a stoppoint', async () => {
      const input_data = mockdata.add_stoppoint_simple.input
      const expected_result = {...mockdata.add_stoppoint_simple.expected, data: mockdata.add_stoppoint_simple.expected.data}
      const actual_result = await graph.add_stoppoint(input_data, false)
      expect(actual_result).toMatchObject(expected_result)
    })

  })
})
