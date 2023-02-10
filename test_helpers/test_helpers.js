const check_params = (params, expected_params) => {
  /**
   * Checks that the params object contains the expected params
   * @param {Object} params - params object
   * @param {Object} expected_params - expected params object
   * @returns {Boolean} - true if params contains expected_params
   *
   */
  if (params === undefined) {
    return false
  }
  for (const [key, value] of Object.entries(expected_params)) {
    if (params[key] !== value) {
      return false
    }
  }
  return true
}

module.exports = {
  check_params
}