module.exports = { buildSearchFile, buildSearchMany };

function buildSearchFile(requestParams, context, ee, next) {
  requestParams.json = {
    lang: 'fr',
    nb_car: parseInt(context.vars.nb_car),
    lst_car: context.vars.cars.split(''),
    strict: context.vars.strict === 'true',
    lst_hint: JSON.parse(context.vars.lst_hint),
  };
  return next();
}

function buildSearchMany(requestParams, context, ee, next) {
  requestParams.json = {
    lang: 'fr',
    cars: context.vars.cars,
    lst_hint: JSON.parse(context.vars.lst_hint),
  };
  return next();
}
