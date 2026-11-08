# Cosa topo non può promettere, e perché

topo è costruito per leggere lo stesso file sempre allo stesso modo: gli stessi
byte in ingresso danno lo stesso risultato. Quello che **non** può promettere è che la stessa *geometria*
dia lo stesso risultato dovunque si trovi: ruotata, spostata lontano
dall'origine, specchiata, scritta in un altro ordine. Questa pagina spiega
perché, con le parole più semplici che abbiamo. Non è un difetto di topo: vale
per qualunque programma che decide sì o no su un numero misurato (MAP.md D215).

## 1. Una regola sì/no ha un confine

Per riparare un disegno topo deve decidere, di continuo, sì o no:

- questo salto è abbastanza piccolo da chiuderlo? (salto ≤ tolleranza)
- questi due capi sono lo stesso punto? (distanza ≤ una soglia)
- questo arco è quasi un cerchio intero? (angolo mancante ≤ 2°)

Ogni regola così ha un confine: un numero appena sotto dice sì, uno appena
sopra dice no. Con il confine a 0,5 mm, un salto di 0,49999999999999 mm si chiude
e uno di 0,50000000000001 mm no.

## 2. Muovere un disegno cambia i suoi numeri di un niente

Il computer tiene una coordinata con circa 16 cifre significative. 0,5 lo scrive
esatto; ma un salto non si legge, si calcola dalle coordinate (coseni, seni,
radici), e ogni passo arrotonda al numero più vicino che il computer sa scrivere:
a volte un pelo sopra, a volte un pelo sotto. Su un pezzo a circa 1000 mm
dall'origine l'errore è di circa 0,00000000000008 mm.

Un salto di 0,5 mm a 1000 mm dall'origine, ruotato e rimisurato:

| rotazione | il salto misura | con il confine a 0,5 |
|---|---|---|
| nessuna | 0,5 | si chiude |
| 20° | 0,49999999999992 | si chiude |
| 45° | 0,50000000000008 | non si chiude |

Il disegno è lo stesso; la risposta no. (topo mette il confine un milionesimo di
mm più in là, a 0,500001, e i tre qui sopra si chiudono tutti; ma un salto che
misura proprio 0,500001 ha lo stesso problema: vedi la sezione 3.)

## 3. Spostare il confine non serve

"Allora confrontiamo con ± 0,00000001." Il confine va a 0,50000001 mm, e un
buco largo esattamente così ha lo stesso problema. Qualunque regola con un sì e
un no ha un punto dove l'uno diventa l'altro, e l'arrotondamento di un moto può
spingere un numero dall'altra parte. Nessun numero di cifre e nessun linguaggio
(C, Rust, Python usano gli stessi numeri a 64 bit, IEEE 754) toglie il confine.

Lo stesso succede quando si raggruppano punti: A è vicino a B, B è vicino a C,
ma A è lontano da C. Se i tre diventano un punto solo è una decisione sì/no, e
ha il suo confine.

## 4. Cosa si può fare: pochi confini, non zero

Quanto spesso succede dipende da quanti confini ci sono.

- **Una griglia di arrotondamento ha confini dappertutto.** Arrotondare ogni
  punto a 0,001 mm mette un confine ogni millesimo di millimetro: due capi a
  0,0004 mm cadono nella stessa casella o in due caselle vicine a seconda di
  dove sta il disegno. Succede su disegni normali, di continuo.
- **Una regola sulla distanza ha un confine per soglia.** Due capi sono lo
  stesso punto se sono più vicini della soglia, misurata come distanza, che un
  moto non cambia. La risposta si ribalta solo per un valore a circa
  0,00000000000001 mm dalla soglia. Quanto spesso succeda nei disegni veri non
  è misurato; zero non è mai.

Per questo topo ha lasciato la griglia per la distanza (MAP.md D216): un nodo è
il punto vero, e due capi sono un nodo solo quando sono abbastanza vicini.

## 5. Cosa vuol dire per chi lo usa

- Stesso file, stesso risultato: topo è costruito così (niente caso, niente
  dipendenza dall'ordine degli hash) ed è quello che i test controllano. Un
  file dove non vale è un difetto da segnalare.
- Stessa geometria dovunque, stesso risultato: non è promesso. Qualunque
  disegno può avere un valore su un confine, e nessun programma può promettere
  il contrario.
- Quando una decisione cade su un confine la differenza si può vedere: un buco
  chiuso in una posizione resta aperto nell'altra, e un contorno che c'è in una
  lettura può mancare nell'altra.
