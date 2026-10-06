module.exports = { buildSearchFile, buildSearchMany };

function buildSearchFile(requestParams, context, ee, next) {
  requestParams.json = {
    lang: 'fr',
    wordLength: parseInt(context.vars.wordLength),
    letters: context.vars.letters.split(''),
    strict: context.vars.strict === 'true',
    hints: JSON.parse(context.vars.hints),
  };
  return next();
}

function buildSearchMany(requestParams, context, ee, next) {
  requestParams.json = {
    lang: 'fr',
    letters: context.vars.letters,
    hints: JSON.parse(context.vars.hints),
  };
  return next();
}
