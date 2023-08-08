import * as mongo from '../mongo';

describe('mongo', () => {
  test.skip('mongo.run', async () => {
    const x = await mongo.run().catch(console.dir)
    expect(x).toBe("Connected successfully to server")
  })
})