const { execSync } = require('child_process')
const config = require('../ts-to-zod.config.js')

try {
  config.forEach(entry => {
    const command = `npx ts-to-zod --config ${entry.name}`
    console.log(`Running: ${command}`)
    execSync(command, { stdio: 'inherit' })
  })

  console.log('All commands executed successfully.')
  process.exit(0) // Exit with success status code
} catch (error) {
  console.error('An error occurred while executing the commands:', error.message)
  process.exit(1) // Exit with failure status code
}
