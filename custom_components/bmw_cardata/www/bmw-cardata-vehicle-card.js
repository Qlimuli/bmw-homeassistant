/**
 * BMW CarData Vehicle Card for Home Assistant
 * A custom Lovelace card for displaying BMW vehicle information
 */

class BMWCarDataVehicleCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  setConfig(config) {
    if (!config.device_id) {
      throw new Error('Please define a device_id');
    }
    this._config = {
      device_id: config.device_id,
      license_plate: config.license_plate || '',
      soc_source: config.soc_source || 'soc',
      show_indicators: config.show_indicators !== false,
      show_range: config.show_range !== false,
      show_image: config.show_image !== false,
      show_map: config.show_map !== false,
      show_buttons: config.show_buttons !== false,
    };
  }

  getCardSize() {
    return 4;
  }

  static getStubConfig() {
    return {
      device_id: '',
      show_indicators: true,
      show_range: true,
      show_image: true,
      show_map: true,
      show_buttons: true,
    };
  }

  findEntitiesByDevice() {
    if (!this._hass || !this._config.device_id) return {};
    
    const entities = {};
    const deviceId = this._config.device_id;
    
    // Find all entities belonging to this device
    Object.keys(this._hass.states).forEach(entityId => {
      if (entityId.startsWith('sensor.') || 
          entityId.startsWith('binary_sensor.') ||
          entityId.startsWith('device_tracker.')) {
        const stateObj = this._hass.states[entityId];
        // Check if entity belongs to our device via attributes
        if (stateObj.attributes && stateObj.attributes.vin) {
          entities[entityId] = stateObj;
        }
      }
    });
    
    return entities;
  }

  getEntityValue(entities, key) {
    for (const [entityId, state] of Object.entries(entities)) {
      if (entityId.includes(key)) {
        return state.state;
      }
    }
    return null;
  }

  getEntityState(entities, key) {
    for (const [entityId, state] of Object.entries(entities)) {
      if (entityId.includes(key)) {
        return state;
      }
    }
    return null;
  }

  render() {
    if (!this._hass || !this._config) return;

    const entities = this.findEntitiesByDevice();
    
    // Get values
    const batteryLevel = this.getEntityValue(entities, 'battery_soc') || 
                         this.getEntityValue(entities, 'battery_level') || 'N/A';
    const electricRange = this.getEntityValue(entities, 'electric_range') || 'N/A';
    const fuelLevel = this.getEntityValue(entities, 'fuel_level') || null;
    const fuelRange = this.getEntityValue(entities, 'fuel_range') || null;
    const mileage = this.getEntityValue(entities, 'mileage') || 
                   this.getEntityValue(entities, 'odometer') || 'N/A';
    const chargingStatus = this.getEntityValue(entities, 'charging_status') || 'N/A';
    const isCharging = this.getEntityValue(entities, 'is_charging') === 'on';
    const chargingPower = this.getEntityValue(entities, 'charging_power') || null;
    
    // Door states
    const doorDriver = this.getEntityValue(entities, 'door_driver') === 'on';
    const doorPassenger = this.getEntityValue(entities, 'door_passenger') === 'on';
    const doorRearLeft = this.getEntityValue(entities, 'door_rear_left') === 'on';
    const doorRearRight = this.getEntityValue(entities, 'door_rear_right') === 'on';
    const trunk = this.getEntityValue(entities, 'trunk') === 'on';
    const hood = this.getEntityValue(entities, 'hood') === 'on';
    
    // Lock state
    const lockState = this.getEntityValue(entities, 'lock_state') || 'N/A';
    const isLocked = lockState.toLowerCase().includes('locked') && 
                     !lockState.toLowerCase().includes('unlocked');
    
    // Location
    const locationState = this.getEntityState(entities, 'location');
    const latitude = locationState?.attributes?.latitude;
    const longitude = locationState?.attributes?.longitude;

    // Get VIN from any entity
    let vin = '';
    for (const state of Object.values(entities)) {
      if (state.attributes?.vin) {
        vin = state.attributes.vin;
        break;
      }
    }

    const html = `
      <style>
        :host {
          --card-background: var(--ha-card-background, var(--card-background-color, white));
          --primary-text: var(--primary-text-color, #212121);
          --secondary-text: var(--secondary-text-color, #727272);
          --accent-color: var(--primary-color, #1a73e8);
          --success-color: #4caf50;
          --warning-color: #ff9800;
          --error-color: #f44336;
        }
        
        .card {
          padding: 16px;
          background: var(--card-background);
          border-radius: var(--ha-card-border-radius, 12px);
        }
        
        .header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
        }
        
        .title {
          font-size: 1.2rem;
          font-weight: 500;
          color: var(--primary-text);
        }
        
        .subtitle {
          font-size: 0.85rem;
          color: var(--secondary-text);
        }
        
        .vehicle-image {
          width: 100%;
          max-height: 200px;
          object-fit: contain;
          margin-bottom: 16px;
          border-radius: 8px;
        }
        
        .vehicle-placeholder {
          width: 100%;
          height: 150px;
          background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
          border-radius: 8px;
          display: flex;
          align-items: center;
          justify-content: center;
          margin-bottom: 16px;
        }
        
        .vehicle-placeholder svg {
          width: 120px;
          height: 80px;
          fill: rgba(255,255,255,0.3);
        }
        
        .indicators {
          display: flex;
          gap: 12px;
          margin-bottom: 16px;
          flex-wrap: wrap;
        }
        
        .indicator {
          display: flex;
          align-items: center;
          gap: 4px;
          padding: 6px 10px;
          background: var(--ha-card-background, #f5f5f5);
          border-radius: 20px;
          font-size: 0.8rem;
        }
        
        .indicator.ok {
          color: var(--success-color);
        }
        
        .indicator.warning {
          color: var(--warning-color);
        }
        
        .indicator.error {
          color: var(--error-color);
        }
        
        .indicator svg {
          width: 16px;
          height: 16px;
        }
        
        .battery-section {
          margin-bottom: 16px;
        }
        
        .battery-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 8px;
        }
        
        .battery-label {
          font-size: 0.9rem;
          color: var(--secondary-text);
        }
        
        .battery-value {
          font-size: 1.5rem;
          font-weight: 600;
          color: var(--primary-text);
        }
        
        .battery-bar {
          height: 24px;
          background: var(--divider-color, #e0e0e0);
          border-radius: 12px;
          overflow: hidden;
          position: relative;
        }
        
        .battery-fill {
          height: 100%;
          border-radius: 12px;
          transition: width 0.3s ease;
        }
        
        .battery-fill.high {
          background: linear-gradient(90deg, #4caf50, #8bc34a);
        }
        
        .battery-fill.medium {
          background: linear-gradient(90deg, #ff9800, #ffc107);
        }
        
        .battery-fill.low {
          background: linear-gradient(90deg, #f44336, #ff5722);
        }
        
        .battery-fill.charging {
          background: linear-gradient(90deg, #2196f3, #00bcd4);
          animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.7; }
        }
        
        .range-info {
          display: flex;
          gap: 16px;
          margin-top: 8px;
        }
        
        .range-item {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 0.85rem;
          color: var(--secondary-text);
        }
        
        .range-item svg {
          width: 18px;
          height: 18px;
        }
        
        .info-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 12px;
          margin-bottom: 16px;
        }
        
        .info-card {
          padding: 12px;
          background: var(--ha-card-background, #f5f5f5);
          border-radius: 8px;
        }
        
        .info-card-label {
          font-size: 0.75rem;
          color: var(--secondary-text);
          margin-bottom: 4px;
        }
        
        .info-card-value {
          font-size: 1rem;
          font-weight: 500;
          color: var(--primary-text);
        }
        
        .map-container {
          width: 100%;
          height: 150px;
          border-radius: 8px;
          overflow: hidden;
          margin-bottom: 16px;
        }
        
        .map-container iframe {
          width: 100%;
          height: 100%;
          border: none;
        }
        
        .map-placeholder {
          width: 100%;
          height: 150px;
          background: #e0e0e0;
          border-radius: 8px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--secondary-text);
          font-size: 0.9rem;
        }
        
        .door-diagram {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 4px;
          max-width: 200px;
          margin: 0 auto 16px;
        }
        
        .door-item {
          padding: 8px;
          text-align: center;
          font-size: 0.7rem;
          border-radius: 4px;
          background: var(--ha-card-background, #f5f5f5);
        }
        
        .door-item.open {
          background: var(--error-color);
          color: white;
        }
        
        .door-item.closed {
          background: var(--success-color);
          color: white;
        }
        
        .charging-info {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 12px;
          background: linear-gradient(135deg, #2196f3 0%, #00bcd4 100%);
          border-radius: 8px;
          color: white;
          margin-bottom: 16px;
        }
        
        .charging-info svg {
          width: 24px;
          height: 24px;
          fill: white;
        }
        
        .charging-text {
          flex: 1;
        }
        
        .charging-power {
          font-size: 1.2rem;
          font-weight: 600;
        }
      </style>
      
      <ha-card>
        <div class="card">
          <div class="header">
            <div>
              <div class="title">BMW ${this._config.license_plate || vin.slice(-6)}</div>
              <div class="subtitle">${vin}</div>
            </div>
            <div class="indicator ${isLocked ? 'ok' : 'warning'}">
              <svg viewBox="0 0 24 24">
                <path fill="currentColor" d="${isLocked 
                  ? 'M12,17A2,2 0 0,0 14,15C14,13.89 13.1,13 12,13A2,2 0 0,0 10,15A2,2 0 0,0 12,17M18,8A2,2 0 0,1 20,10V20A2,2 0 0,1 18,22H6A2,2 0 0,1 4,20V10C4,8.89 4.9,8 6,8H7V6A5,5 0 0,1 12,1A5,5 0 0,1 17,6V8H18M12,3A3,3 0 0,0 9,6V8H15V6A3,3 0 0,0 12,3Z'
                  : 'M18,8A2,2 0 0,1 20,10V20A2,2 0 0,1 18,22H6A2,2 0 0,1 4,20V10C4,8.89 4.9,8 6,8H7V6A5,5 0 0,1 12,1A5,5 0 0,1 17,6H15A3,3 0 0,0 12,3A3,3 0 0,0 9,6V8H18M12,17A2,2 0 0,0 14,15C14,13.89 13.1,13 12,13A2,2 0 0,0 10,15A2,2 0 0,0 12,17Z'
                }"/>
              </svg>
              ${isLocked ? 'Locked' : 'Unlocked'}
            </div>
          </div>
          
          ${this._config.show_image ? `
            <div class="vehicle-placeholder">
              <svg viewBox="0 0 512 512">
                <path d="M499.99 176h-59.87l-16.64-41.6C406.38 91.63 365.57 64 319.5 64h-127c-46.06 0-86.88 27.63-103.99 70.4L71.87 176H12.01C4.2 176-1.53 183.34.37 190.91l6 24C7.7 220.25 12.5 224 18.01 224h20.07C24.65 235.73 16 252.78 16 272v48c0 16.12 6.16 30.67 16 41.93V416c0 17.67 14.33 32 32 32h32c17.67 0 32-14.33 32-32v-32h256v32c0 17.67 14.33 32 32 32h32c17.67 0 32-14.33 32-32v-54.07c9.84-11.25 16-25.8 16-41.93v-48c0-19.22-8.65-36.27-22.07-48H494c5.51 0 10.31-3.75 11.64-9.09l6-24c1.89-7.57-3.84-14.91-11.65-14.91zm-352.06-17.83c7.29-18.22 24.94-30.17 44.57-30.17h127c19.63 0 37.28 11.95 44.57 30.17L384 208H128l19.93-49.83zM96 319.8c-19.2 0-32-12.76-32-31.9S76.8 256 96 256s48 28.71 48 47.85-28.8 15.95-48 15.95zm320 0c-19.2 0-48 3.19-48-15.95S396.8 256 416 256s32 12.76 32 31.9-12.8 31.9-32 31.9z"/>
              </svg>
            </div>
          ` : ''}
          
          ${isCharging ? `
            <div class="charging-info">
              <svg viewBox="0 0 24 24">
                <path d="M12.67,4H11V2H5V4H6.33A1.67,1.67 0 0,0 8,5.67V8C8,8.55 7.55,9 7,9V11C7.55,11 8,11.45 8,12V14.33A1.67,1.67 0 0,1 6.33,16H5V18H11V16H12.67A1.67,1.67 0 0,0 14.33,14.33V12C14.33,11.45 13.88,11 13.33,11V9C13.88,9 14.33,8.55 14.33,8V5.67A1.67,1.67 0 0,0 12.67,4M12.67,8H11.33V6H12.67V8M12.67,14H11.33V12H12.67V14M16,6V18H18V6H16M20,8V16H22V8H20Z"/>
              </svg>
              <div class="charging-text">
                <div>Charging</div>
                ${chargingPower ? `<div class="charging-power">${chargingPower} kW</div>` : ''}
              </div>
              <div>${chargingStatus}</div>
            </div>
          ` : ''}
          
          ${this._config.show_indicators ? `
            <div class="indicators">
              <div class="indicator ${!doorDriver && !doorPassenger && !doorRearLeft && !doorRearRight ? 'ok' : 'error'}">
                <svg viewBox="0 0 24 24">
                  <path fill="currentColor" d="M19,19V5L14,5V19H19M3,19H13V17H5V16L8.5,14.5L5,13V12H13V5H3V19Z"/>
                </svg>
                ${!doorDriver && !doorPassenger && !doorRearLeft && !doorRearRight ? 'Doors closed' : 'Door open'}
              </div>
              <div class="indicator ${!trunk ? 'ok' : 'error'}">
                <svg viewBox="0 0 24 24">
                  <path fill="currentColor" d="M5,9H19A2,2 0 0,1 21,11V20H3V11A2,2 0 0,1 5,9M5,6V4H19V6H5Z"/>
                </svg>
                ${!trunk ? 'Trunk closed' : 'Trunk open'}
              </div>
              <div class="indicator ${!hood ? 'ok' : 'warning'}">
                <svg viewBox="0 0 24 24">
                  <path fill="currentColor" d="M5,13L6.5,8.5H17.5L19,13M17.5,18A1.5,1.5 0 0,1 16,16.5A1.5,1.5 0 0,1 17.5,15A1.5,1.5 0 0,1 19,16.5A1.5,1.5 0 0,1 17.5,18M6.5,18A1.5,1.5 0 0,1 5,16.5A1.5,1.5 0 0,1 6.5,15A1.5,1.5 0 0,1 8,16.5A1.5,1.5 0 0,1 6.5,18M18.92,8L17.5,3H6.5L5.08,8H3V13H4V18H7V20H9V18H15V20H17V18H20V13H21V8H18.92Z"/>
                </svg>
                ${!hood ? 'Hood closed' : 'Hood open'}
              </div>
            </div>
          ` : ''}
          
          ${this._config.show_range ? `
            <div class="battery-section">
              <div class="battery-header">
                <span class="battery-label">Battery</span>
                <span class="battery-value">${batteryLevel}%</span>
              </div>
              <div class="battery-bar">
                <div class="battery-fill ${isCharging ? 'charging' : (parseFloat(batteryLevel) > 50 ? 'high' : parseFloat(batteryLevel) > 20 ? 'medium' : 'low')}" 
                     style="width: ${Math.min(100, Math.max(0, parseFloat(batteryLevel) || 0))}%"></div>
              </div>
              <div class="range-info">
                <div class="range-item">
                  <svg viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12.67,4H11V2H5V4H6.33A1.67,1.67 0 0,0 8,5.67V8C8,8.55 7.55,9 7,9V11C7.55,11 8,11.45 8,12V14.33A1.67,1.67 0 0,1 6.33,16H5V18H11V16H12.67A1.67,1.67 0 0,0 14.33,14.33V12C14.33,11.45 13.88,11 13.33,11V9C13.88,9 14.33,8.55 14.33,8V5.67A1.67,1.67 0 0,0 12.67,4Z"/>
                  </svg>
                  ${electricRange} km
                </div>
                ${fuelRange ? `
                  <div class="range-item">
                    <svg viewBox="0 0 24 24" fill="currentColor">
                      <path d="M18,10A1,1 0 0,1 19,11A1,1 0 0,1 18,12A1,1 0 0,1 17,11A1,1 0 0,1 18,10M18,8A3,3 0 0,0 15,11A3,3 0 0,0 18,14A3,3 0 0,0 21,11A3,3 0 0,0 18,8M12,4A8,8 0 0,0 4,12A8,8 0 0,0 12,20A8,8 0 0,0 20,12A8,8 0 0,0 12,4M12,18A6,6 0 0,1 6,12A6,6 0 0,1 12,6A6,6 0 0,1 18,12A6,6 0 0,1 12,18Z"/>
                    </svg>
                    ${fuelRange} km (fuel)
                  </div>
                ` : ''}
              </div>
            </div>
          ` : ''}
          
          ${this._config.show_buttons ? `
            <div class="info-grid">
              <div class="info-card">
                <div class="info-card-label">Mileage</div>
                <div class="info-card-value">${mileage !== 'N/A' ? `${parseFloat(mileage).toLocaleString()} km` : 'N/A'}</div>
              </div>
              <div class="info-card">
                <div class="info-card-label">Status</div>
                <div class="info-card-value">${chargingStatus}</div>
              </div>
            </div>
          ` : ''}
          
          ${this._config.show_map && latitude && longitude ? `
            <div class="map-container">
              <iframe src="https://www.openstreetmap.org/export/embed.html?bbox=${longitude-0.01},${latitude-0.01},${longitude+0.01},${latitude+0.01}&layer=mapnik&marker=${latitude},${longitude}"></iframe>
            </div>
          ` : this._config.show_map ? `
            <div class="map-placeholder">
              Location not available
            </div>
          ` : ''}
        </div>
      </ha-card>
    `;

    this.shadowRoot.innerHTML = html;
  }
}

customElements.define('bmw-cardata-vehicle-card', BMWCarDataVehicleCard);

// Register card with Home Assistant
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'bmw-cardata-vehicle-card',
  name: 'BMW CarData Vehicle',
  description: 'A card to display BMW vehicle information from CarData',
  preview: true,
  documentationURL: 'https://github.com/your-username/bmw-cardata-hacs',
});

console.info(
  '%c BMW-CARDATA-VEHICLE-CARD %c Version 1.0.0 ',
  'color: white; background: #1a73e8; font-weight: bold;',
  'color: #1a73e8; background: white; font-weight: bold;'
);
