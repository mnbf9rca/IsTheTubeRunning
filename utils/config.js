require('dotenv-vault-core').config()


const PORT = process.env.PORT || 8081
const is_non_production = process.env.NODE_ENV !== ('prod' || 'production')
const TFL_APP_KEY = get_envvar_or_throw('TFL_APP_KEY')
const version='1.0.0'
const service_name='tfl_poller_service'
const tfl_api_root = 'https://api.tfl.gov.uk'
const GRAPH_DATABASE_ENDPOINT = get_envvar_or_throw('GRAPH_DATABASE_ENDPOINT')
const graph_primary_key = get_envvar_or_throw('GRAPH_PRIMARY_KEY')
const graph_database = get_envvar_or_throw('GRAPH_DATABASE_NAME')
const graph_stoppoint_colleciton = 'stoppoints'
const eventhub_sender_connection_string = get_envvar_or_throw('cynexia_tube_sender_EVENTHUB')
const eventhub_name = get_envvar_or_throw('EVENTHUB_NAME')


function get_envvar_or_throw(envvar_name) {
  const envvar = process.env[envvar_name]
  if (!envvar) {
    throw new Error(`Environment variable ${envvar_name} is not set`)
  }
  return envvar
}

module.exports = {
  PORT,
  is_non_production,
  TFL_APP_KEY,
  version,
  service_name,
  tfl_api_root,
  GRAPH_DATABASE_ENDPOINT,
  graph_primary_key,
  graph_database,
  graph_stoppoint_colleciton,
  eventhub_sender_connection_string,
  eventhub_name
}