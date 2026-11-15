# Archivio scaricabile del progetto (progetto.zip)

Un file `progetto.zip` con tutto il codice dell'app AIB Gattinara (esclusa solo la cartella `node_modules`).
Si scarica direttamente dall'anteprima, all'indirizzo https://aib-ore--5n5brlmf.preview.emergentagent.com/progetto.zip

## Per chi è
Per il responsabile del progetto, che vuole una copia completa dei file. Può servire come backup, per consegnarla a un altro sviluppatore o per pubblicarla altrove.

## Funzionalità ed esperienza
- Un solo archivio `progetto.zip` con tutti i file del progetto: backend, frontend, test, documentazione (SPEC, credenziali di prova), configurazioni e cartelle tecniche (cronologia git, cache, risultati dei test, screenshot).
- **Esclusa solo** la cartella `node_modules`, ovunque si trovi. Lo zip non include sé stesso.
- **Inclusi, come richiesto:** il file `backend/.env`, con la chiave segreta delle sessioni, e `memory/test_credentials.md`, con le password di prova e quella provvisoria di Alessia.
- Il file resta nella cartella pubblica anche dopo il download.

## Flusso
1. Si apre il link `…/progetto.zip` nel browser, oppure lo si incolla nella barra degli indirizzi.
2. Il browser scarica il file.
3. Si estrae l'archivio sul computer.

## Aspetto
Nessuna modifica all'interfaccia dell'app: non ci sono pulsanti nuovi, si usa solo il link diretto.

## Fasi
**Fase 1 (MVP, si fa ora)**
- Creare `progetto.zip` con le esclusioni indicate sopra e metterlo nella cartella pubblica dell'app.
- Verificare che il link dell'anteprima scarichi il file e che l'archivio si apra correttamente.
- Pulizia: eliminare l'account amministratore temporaneo `qa.temp@example.it` (QA Temp). Era stato creato solo per collaudare modifica ed eliminazione volontari, che sono pronte e funzionano.

**Fase 2 (in seguito)**
- Pulsante "Scarica progetto" nella sezione Amministrazione, visibile solo agli amministratori, che crea lo zip aggiornato al momento della richiesta. Così non resta un file pubblico e non diventa obsoleto.

**Fase 3 (in seguito)**
- Backup dei dati: esportazione completa di volontari e ore dal database, da affiancare al backup del codice.

## Assunzioni
- **Chi ha il link può scaricarlo.** Il file è accessibile a chiunque conosca l'indirizzo dell'anteprima, senza login. Dentro ci sono la chiave delle sessioni e le password di prova: chi lo ottiene potrebbe accedere agli account. Questa scelta è stata confermata.
- **Anche nell'app pubblicata.** Se l'app viene pubblicata, la cartella pubblica finisce anche nella versione online, quindi lo zip sarebbe scaricabile dal sito definitivo. Prima della pubblicazione è consigliabile rimuoverlo, e poi cambiare la chiave delle sessioni e la password di Alessia.
- **È una fotografia del momento.** Le modifiche fatte all'app dopo la creazione non sono incluse. Per averle bisogna rigenerare lo zip.
- **Niente dati del database.** Volontari registrati, ore e approvazioni non sono file del progetto, quindi non sono nello zip (vedi fase 3).
- **Contenuto completo.** La cronologia git e le cartelle tecniche sono incluse, quindi il file può essere più grande del solo codice.
- **Prima la pulizia.** L'account temporaneo QA Temp viene eliminato prima di creare lo zip. Restano invece gli altri account di prova e la configurazione decisa da Alessia (lei unica amministratrice).
