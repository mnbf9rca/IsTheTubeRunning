module.exports = {
  // Automatically clear mock calls and instances between every test
  clearMocks: true,
  // add --detectOpenHandles to jest command to see which test is hanging
  detectOpenHandles: true,
  // An array of file extensions your modules use
  moduleFileExtensions: ['js', 'json'],
  reporters: [
    'default',
    ['jest-junit', { outputDirectory: 'coverage', outputName: 'junit.xml' }],
    'github-actions'
  ],
  coveragePathIgnorePatterns: [
    '<rootDir>/dist/',
    '<rootDir>/node_modules/',
    '<rootDir>/docs/',
    '<rootDir>/build/',
    '<rootDir>/controllers/tests/',
    '<rootDir>/controllers/line.create.db.js',
    '<rootDir>/services/tests/',
    '<rootDir>/services/__mocks__/',
    '<rootDir>/utils/tests/',
  ],
  testPathIgnorePatterns: [
    '<rootDir>/dist/',
    '<rootDir>/node_modules/',
    '<rootDir>/docs/',
    '<rootDir>/build/',
  ]
}