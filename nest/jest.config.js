module.exports = {
  testEnvironment: 'node',
  rootDir: '.',
  testMatch: ['<rootDir>/test/**/*.spec.ts'],
  transform: {
    // 151002: ts-jest wants isolatedModules for node16/nodenext, which would
    // break Nest's decorator metadata (TS1272); the warning is cosmetic here.
    '^.+\\.ts$': ['ts-jest', { diagnostics: { ignoreCodes: [151002] } }],
  },
};
