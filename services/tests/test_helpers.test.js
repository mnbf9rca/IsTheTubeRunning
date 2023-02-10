describe('check_params', () => {
  const { check_params } = require('./test_helpers')
  test('check params with all params', () => {
    const params = {
      'app_id': '123',
      'app_key': 'abc'
    }
    const expected = true
    const actual = check_params(params, { app_id: '123' })
    expect(actual).toBe(expected)
  })
  test('check params with null params', () => {
    const params = {
      'app_id': '123',
      'app_key': null
    }
    const expected = true
    const actual = check_params(params, { app_id: '123' })
    expect(actual).toBe(expected)
  })
  test('check params with missing params', () => {
    const params = {
      'app_id': '123',
      'app_key': null
    }
    const expected = false
    const actual = check_params(params, { xyz: '123' })
    expect(actual).toBe(expected)
  })
  test('check params with mismatched value but matching key', () => {
    const params = {
      'app_id': '123',
      'app_key': null
    }
    const expected = false
    const actual = check_params(params, { abc: '456' })
    expect(actual).toBe(expected)
  })
  test('check params with empty params', () => {
    const params = {}
    const expected = false
    const actual = check_params(params, { app_id: '123' })
    expect(actual).toBe(expected)
  }
  )
})