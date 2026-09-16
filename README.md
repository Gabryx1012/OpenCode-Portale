# OpenCode Portale

Un pannello locale per avviare OpenCode nei propri progetti da Windows, macOS e Linux. Usa l'interfaccia web ufficiale di OpenCode per le conversazioni. Il pannello non invia file a un proprio servizio e ascolta soltanto su `127.0.0.1`.

## Windows: avvio da un PC nuovo

1. Scarica lo ZIP completo del progetto da GitHub ed estrailo in una cartella scrivibile, per esempio `Documenti\OpenCode-Portale`.
2. Fai doppio clic su **`Avvia-Tutto.bat`**. Tieni aperta la finestra di avvio mentre usi il pannello.
3. Al primo avvio lo script scarica OpenCode dalla [release ufficiale](https://github.com/anomalyco/opencode/releases/latest), confronta il suo SHA-256 con il digest pubblicato da GitHub e lo estrae nella cartella `bin` del pacchetto. Non servono diritti di amministratore.
4. Il pannello si apre nel browser. Aggiungi il percorso completo di un progetto e premi **Avvia OpenCode**. Configura il provider AI in OpenCode quando richiesto.

Servono Windows 10/11 a 64 bit (x64 o ARM64), PowerShell incluso in Windows e una connessione Internet per il primo download di OpenCode e per l'eventuale provider AI. **Non servono Node.js, Python, Git o npm** per avviare il pacchetto Windows: l'interfaccia è già inclusa nell'eseguibile e OpenCode è distribuito come binario autonomo. Non installiamo software non necessario.

Se il download si interrompe, riavvia `Avvia-Tutto.bat`: l'installazione non sostituisce il binario esistente finché l'archivio non è stato verificato. Per aggiornare OpenCode, elimina soltanto `bin\opencode.exe` e riavvia il BAT; il progetto e le sue conversazioni non sono in quella cartella.

## Avvio dai sorgenti

Serve Python 3.10 o successivo. Non ci sono dipendenze Python da installare.

```bash
python app.py
```

Su Windows puoi anche avviare `Avvia-Windows.cmd`. Su macOS/Linux usa `./avvia.sh` (oppure `bash avvia.sh`). Si apre il browser. Inserisci il percorso completo della cartella del progetto, premi **Aggiungi progetto** e poi **Avvia OpenCode**. Se OpenCode non è presente, premi **Installa OpenCode**: viene scaricato il binario della release ufficiale GitHub, verificato con SHA-256 e installato nello spazio utente. Le credenziali dei provider si configurano poi nell'interfaccia di OpenCode.

Quando il repository sarà su GitHub, il workflow `Build desktop launchers` produrrà anche eseguibili per Windows, macOS Apple Silicon e Linux x64 scaricabili dagli artifact di Actions. Sono build separate: non esiste un unico file eseguibile per tutti i sistemi. Le build macOS e Windows generate automaticamente non sono firmate.

## Ogni computer

Scarica lo ZIP del repository da GitHub su ogni computer ed estrailo, oppure clonalo con Git se Git è già presente. I progetti non vengono copiati dal pannello: scaricali o sincronizzali separatamente. Le credenziali dei provider vanno configurate su ogni computer. L'applicazione funziona localmente, senza esporre OpenCode su Internet.

## Sicurezza e limiti

- Il pannello accetta richieste soltanto dall'host locale e protegge le azioni con un token di sessione. Le richieste ai modelli dipendono dal provider configurato in OpenCode e possono uscire dal computer.
- OpenCode viene avviato con `--hostname 127.0.0.1`; non abilitiamo l'accesso di rete.
- Le release vengono scaricate da `anomalyco/opencode` e confrontate con il digest GitHub quando disponibile.
- Il pannello non contiene un editor AI proprio: apre la web UI ufficiale di OpenCode.
- La selezione di cartelle avviene incollando il percorso completo; il browser non può rivelare automaticamente il percorso assoluto di una cartella locale.

## Sviluppo

```bash
python -m unittest discover -s tests -v
```

Licenza MIT. OpenCode è un progetto separato e conserva la propria licenza.
