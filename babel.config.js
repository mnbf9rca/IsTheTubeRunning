module.exports = {
  //plugins: ['babel-plugin-rewire'],
  presets: [
    '@babel/preset-typescript',
    ['@babel/preset-env', { targets: { node: 'current' } }]
  ]
};