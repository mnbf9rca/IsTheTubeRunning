// implement node-cache
const NodeCache = require( 'node-cache' )
const query_cache = new NodeCache()

module.exports = query_cache