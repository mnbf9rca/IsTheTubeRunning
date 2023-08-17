/**
 * ts-to-zod configuration.
 *
 */
module.exports = [
  {
    name: 'tfl_service',
    input: 'tfl_service/TfLResponseTypes.ts',
    output: 'tfl_service/TfLResponseTypesZod.ts',
  },
  {
    name: 'network',
    input: 'network/NetworkTypes.ts',
    output: 'network/NetworkTypesZod.ts'
  },
]