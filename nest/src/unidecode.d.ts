// The `unidecode` npm package ships no type declarations; it exports a single
// function that transliterates a Unicode string to its closest ASCII form.
declare module 'unidecode' {
  function unidecode(str: string): string;
  export = unidecode;
}
