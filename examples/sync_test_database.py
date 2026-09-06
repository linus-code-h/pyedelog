"""Manuelles Data-Sync-Beispiel für die EDELOG-Testdatenbank ``test``.

Vor dem Ausführen die Werte aus .env.local in die Umgebung laden. Dieses Beispiel
schreibt Daten und gehört nur in eine dafür vorgesehene Testdatenbank.
"""

from edelog import DataSyncClient, DataSyncConfig, SyncRequest


def main() -> None:
    kennung = "beispiel-import-4711"

    auftrag = SyncRequest()
    auftrag.database("test").upsert(
        where={"bauteil": kennung},
        values={
            "bauteil": kennung,
            "anzahl": "1",
            "funktion": "Montage",
            "pos_y9t": "10",
            "produkt": "Beispielprodukt",
        },
    )

    with DataSyncClient(DataSyncConfig.from_env()) as sync:
        antwort = sync.submit(auftrag)

    print(f"Job-ID: {antwort['data']['id']}")
    print(f"Status: {antwort['data']['status']}")
    print("Den Abschluss jetzt in Settings → Data Sync prüfen.")


if __name__ == "__main__":
    main()
