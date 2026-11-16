# EPPExtProcStreamErrors

**Symptôme.** Les flux ext_proc Envoy <-> EPP se terminent en erreur.

## Vérifications

- Logs istio-proxy de la Gateway (Loki dashboard 05).

## Leviers d'optimisation

- `DestinationRule` TLS (insecureSkipVerify) vers le service EPP.
