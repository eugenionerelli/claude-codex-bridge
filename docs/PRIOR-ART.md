# Prior art

Snapshot della ricerca al **1 agosto 2026**. Questo documento distingue tre
cose diverse: conversione in uno store di sessione nativo, import/iniezione di
contesto e collaborazione fra due agenti vivi.

Le righe sotto derivano dalla lettura delle fonti primarie alle versioni
indicate. «Ispezionato» significa che il comportamento è presente nel sorgente o
nella documentazione collegata; non equivale a una certificazione runtime su
ogni combinazione di CLI e sistema operativo. I formati di sessione vendor non
sono un'API cross-provider stabile.

## Convertitori di sessione nativa

Il transcoding Claude Code ↔ Codex è implementato da più progetti indipendenti.

| Progetto e fonte primaria | Ambito osservato | Controlli o caratteristiche osservate |
|---|---|---|
| [`transession` v0.1.3](https://github.com/inmzhang/transession/tree/v0.1.3) | Convertitore Rust dedicato a Claude Code e Codex; scrive nel formato nativo del target e lo avvia. | Dichiara una matrice di compatibilità per versioni precise; va riverificata dopo gli upgrade vendor. |
| [`cross_agent_session_resumer` / CASR, main 0.2.3](https://github.com/Dicklesworthstone/cross_agent_session_resumer) ([versione](https://github.com/Dicklesworthstone/cross_agent_session_resumer/blob/main/Cargo.toml)) | IR canonica con 17 adapter rilevati nell'audit, 15 dei quali scrivibili; include Claude Code e Codex. | Rilegge il target, verifica la fedeltà strutturale e supporta rollback/backup. La [licenza](https://github.com/Dicklesworthstone/cross_agent_session_resumer/blob/main/LICENSE) è MIT con un rider aggiuntivo OpenAI/Anthropic: va letta prima del riuso. |
| [`showagent` v0.11.0](https://github.com/aytzey/showagent/blob/v0.11.0/README.md) | TUI e indice locale per sei store dichiarati: Codex, Claude, Gemini, OpenCode, jcode e Pi. | La conversione usa `x` per anteprima e una seconda `x` per conferma; documenta redazione e pubblicazione atomica. |
| [`opal-bridge`, manifest 0.6.0](https://github.com/1va7/opal-bridge) | Implementazione Python con formato canonico e adapter; include watch/sync, hook e pairing. | Il comando `smoke` copre il percorso di conversione/lancio. Compatibilità con le build vendor correnti e stato della licenza non sono stati stabiliti da questo audit. |
| [`harness-convert` v0.2.2](https://github.com/harshitsinghbhandari/harness-convert/tree/v0.2.2) | Convertitore Python Claude Code/Codex basato sulla libreria standard. | Implementazione concentrata sulla conversione dei formati nativi; nessuna pretesa qui su compatibilità oltre la versione collegata. |
| [`ai-session-bridge` v0.2.0](https://github.com/bakhtiersizhaev/ai-session-bridge/tree/v0.2.0) | Conversione TypeScript bidirezionale Claude/Codex. | Conserva call/result e applica una mappatura best-effort, spesso molti-a-uno, fra strumenti: [Codex → Claude](https://github.com/bakhtiersizhaev/ai-session-bridge/blob/v0.2.0/src/codex2claude.ts), [Claude → Codex](https://github.com/bakhtiersizhaev/ai-session-bridge/blob/v0.2.0/src/claude2codex.ts). |

## Percorsi ufficiali OpenAI

Il comando Codex `/import` è presente almeno dal tag
[`rust-v0.140.0`](https://github.com/openai/codex/blob/rust-v0.140.0/codex-rs/tui/src/slash_command.rs)
e usa l'infrastruttura di migrazione degli agenti esterni. I valori 50 e 30
giorni nel codice corrente sono default per la scoperta delle sessioni candidate
([modello](https://github.com/openai/codex/blob/main/codex-rs/external-agent-migration/src/model.rs)
[discovery](https://github.com/openai/codex/blob/main/codex-rs/external-agent-migration/src/detect/sessions/common.rs));
non sono un limite di 50 elementi del transcript.

Il plugin OpenAI
[`codex-plugin-cc` v1.0.6](https://github.com/openai/codex-plugin-cc/tree/v1.0.6)
espone `/codex:transfer` dentro Claude Code. La sua implementazione
([`codex.mjs`](https://github.com/openai/codex-plugin-cc/blob/v1.0.6/plugins/codex/scripts/lib/codex.mjs))
va considerata separatamente: i default di discovery di `/import` non vanno
attribuiti automaticamente al plugin.

Entrambi coprono il percorso ufficiale Claude → Codex. Nelle fonti Anthropic
esaminate non è stato trovato, alla data di questo snapshot, un importatore
simmetrico Codex → Claude; questa è un'osservazione datata, non una dichiarazione
di assenza assoluta.

## Strumenti adiacenti

[`AgentBridge` v0.1.30](https://github.com/raysonmeng/agent-bridge)
mantiene due sessioni native vive e inoltra messaggi selezionati fra loro. Il
suo caso principale è la revisione incrociata; il quota companion è opzionale.
Persistenza/ripresa delle pair e relay live sono funzionalità sostanziali, ma
non costituiscono transcodifica del transcript storico.

[`ccl`](https://github.com/luongnv89/ccl) importa e redige transcript nel
proprio store, quindi li inietta in un'esecuzione one-shot `-p`. Relay MCP
handoff Markdown e altri one-shot possono trasferire contesto utile senza
creare una nuova sessione nativa interattiva e resumable. Sono modelli
operativi diversi, non versioni «irrilevanti» dello stesso problema.

## Confronto fattuale dei bundle

La matrice confronta i progetti più vicini per modello operativo. `—` significa
«non stabilito nelle fonti esaminate», non prova che la capacità sia assente.

| Capacità | Questo bridge | CASR 0.2.3 | showagent 0.11.0 | opal-bridge 0.6.0 | AgentBridge 0.1.30 |
|---|---|---|---|---|---|
| Nuova sessione nativa Claude ↔ Codex | Sì | Sì | Sì | Implementata; compatibilità corrente non verificata | No: collega due sessioni vive |
| Oltre la coppia Claude/Codex | No | 17 adapter / 15 writer nell'audit | Sei store | Architettura ad adapter | No |
| Verifica dopo scrittura | Verifica identità/prefisso e collisioni | Read-back strutturale con rollback/backup | Pubblicazione atomica documentata | Comando `smoke` | n/a |
| Redazione prima del trasferimento | Sì, best-effort |, | Sì |, | n/a |
| Stato persistente per chat/pair | Lane, session ID e lineage content-addressed |, | Indice delle sessioni | Pairing | Pair nominate e resume |
| Capsule Git/filesystem e controllo drift | Sì |, |, |, |, |
| Watch o collaborazione live | Via integrazione AgentBridge opzionale |, | Conversione interattiva in TUI | Watch/sync e hook | Relay live |

La scelta progettuale qui è quindi un bundle ristretto alla coppia
Claude/Codex: transcodifica nativa, capsule operativa verificata, redazione
lane multi-chat, lineage/idempotenza e apertura diretta. Singole capacità e
combinazioni parziali esistono altrove; la matrice descrive l'integrazione
senza rivendicare unicità assoluta.

## Dettagli di formato: fonti e osservazioni

- **Codex, persistenza e UI.** Il formato contiene elementi destinati al
  contesto (`response_item`) ed eventi usati anche dalla presentazione
  (`event_msg`); si vedano l'[exporter della migrazione](https://github.com/openai/codex/blob/main/codex-rs/external-agent-migration/src/export.rs)
  e il [rollout recorder](https://github.com/openai/codex/blob/main/codex-rs/rollout/src/recorder.rs).
  Nei test locali emettere entrambi ha preservato contesto e scrollback. Le
  fonti non dimostrano un requisito di timestamp identico, quindi non lo
  assumiamo.
- **Segmenti Claude.** Sulle build testate, dopo alcune riprese native i nodi
  mainline possono formare segmenti non collegati da un'unica catena
  `parentUuid`. È un'osservazione empirica: un reader prudente conserva tutti i
  segmenti visibili in ordine e non segue soltanto l'ultima foglia.
- **Tool call interrotte.** Sulle build testate, una vera call serializzata senza
  risultato può disturbare il primo turno dopo il resume. Il problema non si
  applica quando call e output vengono rappresentati come testo; non è qui
  formulato come regola universale dei vendor.
- **Identificativi Codex.** Il tipo ufficiale
  [`ThreadId`](https://github.com/openai/codex/blob/main/codex-rs/protocol/src/thread_id.rs)
  genera UUIDv7; naming e serializzazione dei rollout sono nel
  [`recorder`](https://github.com/openai/codex/blob/main/codex-rs/rollout/src/recorder.rs).
  UUIDv4 e codifica della directory progetto sul lato Claude sono invece
  comportamenti ricavati empiricamente dalle build testate, non un contratto
  Anthropic pubblicato.

Ogni confronto va rieseguito quando cambiano le CLI: la compatibilità con un
formato interno osservato a una versione non implica compatibilità futura.
