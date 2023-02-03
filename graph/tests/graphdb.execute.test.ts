import GraphExecute from '../graphdb.execute'


describe('graphdb.execute tests', () => {
  describe('test helper functions', () => {
    describe('test stringToMilliseconds', () => {
      // const stringToMilliseconds = graph.__get__('stringToMilliseconds')
      test('returns ms when only ms given', () => {
        const input_value = '00:00:00.1040000'
        const expected_result = 104
        const actual_result = GraphExecute.stringToMilliseconds(input_value)
        expect(actual_result).toEqual(expected_result)
      })
      test('returns ms with seconds, hours, minutes', () => {
        const input_value = '01:02:03.1040000'
        const expected_result = 3723104
        const actual_result = GraphExecute.stringToMilliseconds(input_value)
        expect(actual_result).toEqual(expected_result)
      })
      test('returns ms when longer ms given', () => {
        const input_value = '00:00:00.1044678'
        const expected_result = 104
        const actual_result = GraphExecute.stringToMilliseconds(input_value)
        expect(actual_result).toEqual(expected_result)
      })
      test('throws on invalid input', () => {
        const input_value = 'alphabet'
        expect(() => GraphExecute.stringToMilliseconds(input_value)).toThrow()
      })
    })
  })
})
