# Bachelorarbeit_BaseRoverSetup
Die Base-Station leitet Daten unverändert weiter und dient als SSH-Server mit Key-Authentication. Ein zentrales Hub-Programm verbindet sich mit Base und Rover, parst, verwaltet und verteilt alle Daten. Die Base bleibt schlank, alle Analysefunktionen laufen im Hub.


Das System besteht aus einer Base-Station und einem Rover, die gemeinsam ein RTK-Setup bilden. Die Base-Einheit übernimmt dabei keine Datenanalyse. Sie verarbeitet oder interpretiert eingehende Nachrichten nicht, sondern fungiert ausschließlich als transparenter Kommunikationskanal, der alle Daten unverändert weiterleitet.

Die Base dient dabei als SSH-Server, über den der Rover bzw. Client die Rohdaten empfängt. Die Authentifizierung erfolgt ausschließlich über Key-Based Authentication, um einen sicheren und passwortlosen Zugriff zu gewährleisten.

Die eigentliche Datenverarbeitung findet nicht auf der Base statt. Stattdessen gibt es ein eigenständiges Hub-Programm, das sich sowohl mit der Base als auch mit dem Rover verbindet. Dieses mittelständige Programm sammelt, interpretiert, aufbereitet und verwaltet alle eingehenden Datenströme. Es übernimmt das vollständige Parsing der GNSS-, RTCM- und sonstigen Daten und verteilt die ausgewerteten Informationen strukturiert an die jeweiligen Clients, einschließlich des Rovers.

Durch diese Architektur bleibt die Base bewusst schlank und stabil, da sie nur als zuverlässiger Daten-Tunnel fungiert, während alle intelligenten Funktionen, Analyseprozesse und Verwaltungsaufgaben zentral im Hub-Programm ausgeführt werden.


## Verwendung von `Base.py`

`Base.py` fungiert als **Basisstation** für das RTK-System.

### Benötigte Anpassungen

- **Baudrate:** Muss vom Benutzer entsprechend der verwendeten Hardware eingestellt werden.  
- **SSH Private Key:** Der Pfad zum eigenen privaten SSH-Key muss korrekt angegeben werden.  
- **Authorized Keys:** Die Datei `authorized_keys` muss erweitert werden und sich im Scope von `Base.py` befinden. Hier wird überprüft, ob ein Client mit einem bestimmten Username (z. B. `xxx`) eine Verbindung herstellen darf.  
  - Dazu muss eine Datei mit Namen: **Username** und dem **öffentlichen Key** des Clients in die Datei `authorized_keys` eingefügt werden.

## Verwendung des Test-User-Interface (zentrale Verteilstelle)

Das Test-User-Interface fungiert als zentrale Verteilstelle: Es empfängt die Daten der Basisstationen, parst sie und trennt sie in **NMEA**, **RTCM** und **CONFIG-Daten** auf.  
Im Verlauf der Tests sollen diese Daten an die Rover verteilt werden, sodass die Clients die jeweiligen Informationen gezielt nutzen können.


- **PORT:** Muss entsprechend der Server-Einstellung angepasst werden.  
- **FILEPATH:** Pfad zum privaten SSH-Key des Clients.  
- **Username:** Den Benutzernamen des Geräts anpassen.  

Hinweis: Bisher können nur **CONFIG-Daten** übergeben werden; andere Felder haben derzeit keine Wirkung und dienen vorerst nur zum Testen.  
Nach dem Start des Programms können einzelne Felder ausgewählt werden, um die gewünschten Daten anzuzeigen.
 
## Achtung!  
Beim Neustart des Programms müssen sowohl Base als auch das Interface/Rover-Programm neu gestartet werden.  
Reihenfolge beachten:  
1. Base-Server schließen  
2. Base-Server neu starten  
3. Erst danach mit dem Client verbinden

