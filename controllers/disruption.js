const call_tfl = require('../services/tfl_api')
const logger = require('../utils/logger')


async function is_there_disruption() {
  /**
   * Fetches the disruption data from TFL. returns a binary true/false.
   **/

  const disruption = await call_tfl.get_disruption(['tube', 'overground'], false)

  return { is_there_disruption: check_disruption_set_for_disruption(disruption.data), ttl: disruption.ttl }

}

function check_disruption_set_for_disruption(disruption_set) {
  /**
    * checks the severity every lineStatus is 10 (good service)
    * returns false if there is disruption
   */
  const line_disruption = disruption_set.every(line => {
    const disruptions = line.disruptions.every(disruption => {
      return disruption.severity === 10
    }
    )
    return disruptions
  })
  return !line_disruption
}

async function disruption_detail() {
  /**
   * Fetches the disruption data from TFL. returns the detailed disruption data.
   * can be quite large - several MB - as it includes every impacted station
   **/

  const disruption = await call_tfl.get_disruption(['tube','overground','dlr'],true)

  return { disruption }

}

module.exports = { is_there_disruption, disruption_detail, check_disruption_set_for_disruption }