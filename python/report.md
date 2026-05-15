# seek_words Integration Report
_2026-05-15_

## Summary

| # | Test | Count | Time |
|---|------|-------|------|
| 1 | Letters strict — anagrams of 'elisa' | 8 words | 136.52 ms |
| 2 | Letters open — anagrams of 'elisa' | 81 words | 132.46 ms |
| 3 | Hint only — pattern s_a_e | 8 words | 184.88 ms |
| 4 | Letters + 2 hints | 11 words | 257.94 ms |
| 5 | Inverted hints + letters | 37 words | 209.16 ms |
| 6 | Strict + hint — anagrams of 'elisa' with 'a' at pos 3 | 2 words | 285.27 ms |
| 7 | Multi-length — words from 'guillaume' letters | 498 words | 2278.34 ms |
| 8 | Multi-length with hint — words from 'guillaume' letters with 'a' at pos 4 | 35 words | 5949.94 ms |

---

## Details

### 1. Letters strict — anagrams of 'elisa'

_5-letter French words that are exact anagrams of 'elisa' (each letter used once)_

**Params**: `lang=fr, nb_car=5, lst_car=list('elisa'), strict=True`  
**Time**: 136.52 ms | **Count**: 8

`ailes`, `ailés`, `alise`, `asile`, `laies`, `lesai`, `lésai`, `salie`

### 2. Letters open — anagrams of 'elisa'

_5-letter French words that are exact anagrams of 'elisa' (may repeat letters)_

**Params**: `lang=fr, nb_car=5, lst_car=list('elisa'), strict=False`  
**Time**: 132.46 ms | **Count**: 81

`ailee`, `ailée`, `ailes`, `ailés`, `ailla`, `aille`, `aillé`, `aisee`, `aisée`, `aises`, `aisés`, `aleas`, `aléas`, `alesa`, `alese`, `alésé`, `alias`, `alise`, `allai`, `allas`, `allee`, `allée`, `alles`, `allés`, `allia`, `allie`, `allié`, `asile`, `assai`, `asses`, `assis`, `eleis`, `éléis`, `elise`, `élise`, `elles`, `essai`, `esses`, `ileal`, `iléal`, `laies`, `lassa`, `lasse`, `lassé`, `lesai`, `lésai`, `lesas`, `lésas`, `lesee`, `lésée`, `leses`, `lèses`, `lésés`, `liais`, `liees`, `liées`, `lilas`, `lises`, `lissa`, `lisse`, `lissé`, `saisi`, `salai`, `salas`, `salee`, `salée`, `sales`, `salés`, `salie`, `salis`, `salle`, `salsa`, `salse`, `sassa`, `sasse`, `sassé`, `sella`, `selle`, `sellé`, `sisal`, `sises`

### 3. Hint only — pattern s_a_e

_5-letter words with 's' at pos 1, 'a' at pos 3, 'e' at pos 5_

**Params**: `lang=fr, nb_car=5, lst_hint=[Hint(1,'s'), Hint(3,'a'), Hint(5,'e')]`  
**Time**: 184.88 ms | **Count**: 8

`scare`, `skate`, `slave`, `stade`, `stage`, `stase`, `suage`, `suave`

### 4. Letters + 2 hints

_5-letter words from 'elisa' letters, starting with 'l' and ending with 's'_

**Params**: `lang=fr, nb_car=5, lst_car=list('elisa'), lst_hint=[Hint(1,'l'), Hint(5,'s')]`  
**Time**: 257.94 ms | **Count**: 11

`laies`, `lesas`, `lésas`, `leses`, `lèses`, `lésés`, `liais`, `liees`, `liées`, `lilas`, `lises`

### 5. Inverted hints + letters

_5-letter words from 'elisa' letters, 'l' not at pos 1, 'e' not at pos 3_

**Params**: `lang=fr, nb_car=5, lst_car=list('elisa'), lst_hint=[Hint(1,'l',inverted=True), Hint(3,'e',inverted=True)]`  
**Time**: 209.16 ms | **Count**: 37

`ailee`, `ailée`, `ailes`, `ailés`, `ailla`, `aille`, `aillé`, `aisee`, `aisée`, `aises`, `aisés`, `asile`, `assai`, `asses`, `assis`, `essai`, `esses`, `saisi`, `salai`, `salas`, `salee`, `salée`, `sales`, `salés`, `salie`, `salis`, `salle`, `salsa`, `salse`, `sassa`, `sasse`, `sassé`, `sella`, `selle`, `sellé`, `sisal`, `sises`

### 6. Strict + hint — anagrams of 'elisa' with 'a' at pos 3

_Exact anagrams of 'elisa' where the 3rd letter is 'a'_

**Params**: `lang=fr, nb_car=5, lst_car=list('elisa'), lst_hint=[Hint(3,'a')], strict=True`  
**Time**: 285.27 ms | **Count**: 2

`lesai`, `lésai`

### 7. Multi-length — words from 'guillaume' letters

_Words of any length (1-9) using only the letters from 'guillaume'_

**Params**: `lang=fr, cars='guillaume'`  
**Time**: 2278.34 ms | **Count**: 498

`aiguillai`, `aiguillee`, `aiguillée`, `amalgamai`, `amalgamee`, `amalgamée`, `emaillage`, `émaillage`, `emmiellai`, `emmiellee`, `emmiellée`, `guillaume`, `aiguilla`, `aiguille`, `aiguillé`, `allegeai`, `allégeai`, `alleguai`, `alléguai`, `alleguee`, `alléguée`, `alleluia`, `allumage`, `amalgama`, `amalgame`, `amalgamé`, `égaillai`, `egaillee`, `égaillée`, `égueulée`, `emaillai`, `émaillai`, `emaillee`, `émaillée`, `emmiella`, `emmielle`, `glumelle`, `illegale`, `illégale`, `lamellee`, `lamellée`, `limaille`, `maillage`, `millieme`, `millième`, `aiguail`, `allegea`, `allégea`, `allegee`, `allégée`, `allegie`, `allegua`, `allégua`, `allegue`, `allègue`, `allégué`, `alliage`, `allumai`, `allumee`, `allumée`, `égailla`, `egaille`, `égaille`, `égaillé`, `égueulé`, `elagage`, `élagage`, `elaguai`, `élaguai`, `elaguee`, `élaguée`, `élimage`, `emailla`, `émailla`, `emaille`, `émaille`, `émaillé`, `emmelai`, `emmêlai`, `emmelee`, `emmêlée`, `galgale`, `galilée`, `gallium`, `gamelle`, `gaulage`, `gemelle`, `gemmage`, `gemmail`, `gemmule`, `glaieul`, `glaïeul`, `gueulai`, `gueulee`, `gueulée`, `illegal`, `illégal`, `imageai`, `lamelle`, `liegeai`, `ligulee`, `ligulée`, `liliale`, `maillai`, `maillee`, `maillée`, `mamelle`, `mamelue`, `meuglai`, `meulage`, `miaulai`, `miellee`, `miellée`, `millage`, `agamie`, `aieule`, `aïeule`, `aillai`, `aillee`, `aillée`, `allege`, `allège`, `allégé`, `allegi`, `allèle`, `alliai`, `alliee`, `alliée`, `alluma`, `allume`, `allumé`, `aumale`, `egalai`, `égalai`, `egalee`, `égalée`, `elagua`, `élagua`, `elague`, `élague`, `élagué`, `elegie`, `élégie`, `elimai`, `elimee`, `élimée`, `emmela`, `emmêla`, `emmele`, `emmêle`, `emmêlé`, `emulai`, `emulee`, `gageai`, `galgal`, `gammee`, `gammée`, `gaulai`, `gaulee`, `gaulée`, `gaulle`, `gelule`, `gélule`, `gemeau`, `gémeau`, `gemmai`, `gemmee`, `gemmée`, `gliale`, `gueula`, `gueule`, `ileale`, `iléale`, `imagea`, `imagee`, `imagée`, `lamage`, `legale`, `légale`, `leguai`, `léguai`, `leguee`, `léguée`, `legume`, `légume`, `liegea`, `liegee`, `liégée`, `liguai`, `liguee`, `liguée`, `ligule`, `lilial`, `limage`, `limule`, `lugeai`, `mailla`, `maille`, `maillé`, `malaga`, `mamelu`, `meugla`, `meugle`, `meuglé`, `meulai`, `meulee`, `miaula`, `miaule`, `mielle`, `miellé`, `milieu`, `ululai`, `agami`, `agile`, `aieul`, `aïeul`, `aigle`, `aigue`, `aiguë`, `ailee`, `ailée`, `ailla`, `aille`, `aillé`, `aimai`, `aimee`, `aimée`, `algie`, `algue`, `allai`, `allee`, `allée`, `alleu`, `allia`, `allie`, `allié`, `almee`, `almée`, `amuie`, `augée`, `egaie`, `égaie`, `egala`, `égala`, `egale`, `égale`, `égalé`, `élami`, `elegi`, `élégi`, `elima`, `elime`, `élimé`, `email`, `émail`, `emiai`, `emiee`, `emula`, `emule`, `émule`, `gagea`, `gagee`, `gagée`, `galle`, `gamma`, `gamme`, `gaula`, `gaule`, `gelai`, `gelee`, `gelée`, `gemie`, `gemma`, `gemme`, `gigue`, `gille`, `glial`, `gluau`, `glume`, `gueai`, `gueee`, `igame`, `ileal`, `iléal`, `image`, `imagé`, `lamai`, `lamee`, `lamée`, `lamie`, `legal`, `légal`, `legua`, `légua`, `legue`, `lègue`, `légué`, `lemme`, `liage`, `liege`, `liège`, `liégé`, `lieue`, `ligie`, `ligua`, `ligue`, `ligué`, `limai`, `limee`, `limée`, `lugea`, `magie`, `magma`, `malle`, `mamie`, `megie`, `melai`, `mêlai`, `melee`, `mêlée`, `melia`, `mélia`, `meula`, `meule`, `miami`, `mille`, `milli`, `mimai`, `mimee`, `mimée`, `ulema`, `uléma`, `ulula`, `ulule`, `ululé`, `agee`, `âgée`, `agui`, `aigu`, `aile`, `ailé`, `aima`, `aime`, `aimé`, `alea`, `aléa`, `alla`, `alle`, `allé`, `alma`, `amie`, `amui`, `auge`, `egal`, `égal`, `elle`, `elue`, `élue`, `emeu`, `émeu`, `emia`, `emie`, `emue`, `émue`, `gaga`, `gage`, `gagé`, `gaie`, `gala`, `gale`, `geai`, `gela`, `gele`, `gèle`, `gelé`, `gemi`, `gémi`, `glui`, `guai`, `guea`, `guee`, `igue`, `imam`, `iule`, `laie`, `lama`, `lame`, `lamé`, `lege`, `lège`, `liai`, `liee`, `liée`, `lieu`, `lige`, `lima`, `lime`, `limé`, `luge`, `lulu`, `mage`, `maia`, `maïa`, `maie`, `mail`, `male`, `mâle`, `mali`, `megi`, `mela`, `mêla`, `mele`, `mêle`, `mêlé`, `meme`, `même`, `miel`, `mile`, `mima`, `mime`, `mimé`, `mimi`, `mlle`, `muai`, `muee`, `muée`, `muge`, `mugi`, `mule`, `age`, `âge`, `âgé`, `agi`, `aie`, `aïe`, `ail`, `ale`, `ame`, `âme`, `ami`, `eau`, `elu`, `élu`, `eme`, `ème`, `emu`, `ému`, `eue`, `gag`, `gai`, `gal`, `gel`, `glu`, `gue`, `gué`, `gui`, `ile`, `île`, `lai`, `lei`, `leu`, `lia`, `lie`, `lié`, `lue`, `lui`, `mai`, `mal`, `mie`, `mil`, `mme`, `mua`, `mue`, `mué`, `ulm`, `ai`, `aï`, `au`, `eu`, `il`, `la`, `là`, `le`, `lé`, `li`, `lu`, `ma`, `me`, `mg`, `mi`, `ml`, `mm`, `mu`, `mû`, `a`, `à`, `l`, `u`

### 8. Multi-length with hint — words from 'guillaume' letters with 'a' at pos 4

_Words of any length (1-9) using only the letters from 'guillaume', with 'a' at position 4_

**Params**: `lang=fr, cars='guillaume', lst_hint=[Hint(4, 'a'),Hint(1, 'a', inverted=True)]`  
**Time**: 5949.94 ms | **Count**: 35

`limaille`, `gliale`, `ileale`, `iléale`, `lamage`, `legale`, `légale`, `limage`, `malaga`, `emiai`, `gelai`, `glial`, `gluau`, `gueai`, `ileal`, `iléal`, `lamai`, `legal`, `légal`, `limai`, `melai`, `mêlai`, `mimai`, `emia`, `gaga`, `gala`, `gela`, `guea`, `lama`, `lima`, `maia`, `maïa`, `mela`, `mêla`, `mima`
