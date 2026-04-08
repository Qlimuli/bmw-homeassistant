# BMW CarData Integration for Home Assistant

Eine HACS-Integration für BMW-Fahrzeuge, die die offizielle **BMW CarData API** nutzt - funktioniert auch nach der Abschaltung der alten MyBMW-Integration.

## Features

### Sensoren
- **Batterie/Laden**: Ladestand (SOC), Ladeleistung, Ladezeit, Ladeziel, Ladestatus
- **Reichweite**: Elektrische Reichweite, Kraftstoffreichweite (PHEV/ICE)
- **Kraftstoff**: Tankfüllstand, verbleibender Kraftstoff
- **Kilometerstand**: Aktueller Kilometerstand
- **Standort**: GPS-Position mit Höhe und Richtung
- **Klima**: Innen- und Außentemperatur
- **Geschwindigkeit**: Aktuelle Geschwindigkeit
- **Reifendruck**: Alle vier Reifen

### Binäre Sensoren
- Türen (Fahrer, Beifahrer, hinten links/rechts)
- Kofferraum und Motorhaube
- Fenster-Status
- Verriegelungsstatus
- Ladestatus (lädt/eingesteckt)
- Bewegungsstatus

### Geräte-Tracker
- GPS-Position mit Karte
- Geschwindigkeit und Richtung als Attribute

### Lovelace Card
- Integrierte Fahrzeugkarte mit Echtzeitdaten
- Batteriestand mit Farbverlauf
- Tür-/Fenster-Status
- Kartenansicht des Standorts

## Installation

### HACS (Empfohlen)

1. HACS öffnen
2. **Integrationen** -> **Custom Repositories** 
3. Repository-URL hinzufügen und Kategorie "Integration" wählen
4. "BMW CarData" suchen und installieren
5. Home Assistant neustarten

### Manuell

1. Ordner `custom_components/bmw_cardata` in Ihren `config/custom_components` Ordner kopieren
2. Home Assistant neustarten

## BMW Portal Setup (WICHTIG - VOR der HA-Installation)

### Schritt 1: BMW Portal öffnen
- BMW: https://www.bmw.de/de-de/mybmw/vehicle-overview
- Mini: https://www.mini.de/de-de/mymini/vehicle-overview

### Schritt 2: CarData Client erstellen
1. Fahrzeug auswählen
2. **BMW CarData** wählen
3. **Create CarData Client** klicken
4. **Client ID kopieren** (wird später benötigt!)

### Schritt 3: API-Zugriff aktivieren
1. **"Request access to CarData API"** klicken
2. **60 Sekunden warten**
3. **"Request access to CarData Stream"** klicken
4. **60 Sekunden warten**

### Schritt 4: Telematik-Daten konfigurieren
1. **"Configure data stream"** klicken
2. Alle gewünschten Deskriptoren aktivieren
3. **Speichern**

**JavaScript-Tipp zum Aktivieren aller Deskriptoren:**
```javascript
document.querySelectorAll('label.chakra-checkbox:not([data-checked])').forEach(l => l.click());
```

## Home Assistant Konfiguration

1. **Einstellungen** -> **Geräte & Dienste** -> **Integration hinzufügen**
2. **BMW CarData** suchen
3. **Client ID** eingeben (aus Schritt 2)
4. **Verifizierungs-Link** öffnen und **Code** eingeben
5. **Warten** bis BMW die Autorisierung bestätigt
6. Erst DANN auf **Absenden** klicken

## Verfügbare Entitäten

Nach erfolgreicher Einrichtung werden folgende Entitäten erstellt:

| Entitätstyp | Entitäten |
|-------------|-----------|
| Sensoren | Batteriestand, Reichweite, Kilometerstand, Temperatur, Reifendruck, etc. |
| Binäre Sensoren | Türen, Fenster, Schlösser, Ladestatus |
| Geräte-Tracker | GPS-Position |
| Buttons | Daten aktualisieren, Tokens erneuern |

## Lovelace Card

Die Integration enthält eine eingebaute Lovelace-Karte:

```yaml
type: custom:bmw-cardata-vehicle-card
device_id: <ihre_geräte_id>
license_plate: AB 123 CD
show_indicators: true
show_range: true
show_image: true
show_map: true
show_buttons: true
```

## API Rate Limits

BMW begrenzt API-Aufrufe auf **50 pro Tag**. Die Integration minimiert API-Aufrufe durch:

- **MQTT-Streaming** für Echtzeit-Updates (unbegrenzt)
- **Intelligentes Polling** als Fallback
- **Token-Caching** zur Vermeidung unnötiger Auth-Aufrufe

## Fehlerbehebung

### Error 403 (Forbidden)
- Client ID überprüfen
- CarData API UND CarData Stream aktiviert?
- 2-3 Minuten nach Aktivierung warten

### Error 500 (Server Error)
- Integration entfernen
- Neue Client ID erstellen
- 5 Minuten warten
- Erneut einrichten

### Keine Daten
- MyBMW App öffnen und Tür ver-/entriegeln (löst Update aus)
- Bei älteren Fahrzeugen (iDrive 6): Kurze Fahrt nötig

## Technische Details

### Unterstützte Plattformen
- sensor
- binary_sensor
- device_tracker
- button

### Abhängigkeiten
- paho-mqtt >= 2.0.0
- Home Assistant >= 2026.1.0

### Unterstützte Regionen
- EU (primär)
- USA (experimentell)

## Credits

Diese Integration basiert auf der offiziellen BMW CarData API Dokumentation:
https://bmw-cardata.bmwgroup.com/customer/public/api-documentation/Id-Introduction

## Lizenz

BSD 2-Clause License
