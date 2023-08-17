const { execSync } = require('child_process')
const config = require('../ts-to-zod.config.js')

config.forEach(entry => {
  const command = `npx ts-to-zod --config ${entry.name}`
  console.log(`Running: ${command}`)
  execSync(command, { stdio: 'inherit' })
})

console.log('All commands executed successfully.')
