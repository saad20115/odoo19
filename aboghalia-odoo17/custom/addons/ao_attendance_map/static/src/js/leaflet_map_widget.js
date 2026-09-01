/** @odoo-module */

import { registry } from "@web/core/registry";
import { Component, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { loadJS, loadCSS } from "@web/core/assets";

// Check-in widget component
class LeafletMapCheckIn extends Component {
  setup() {
    this.mapRef = useRef("mapContainer");
    onMounted(() => this.initMap());
    onWillUnmount(() => this.cleanup());
  }

  async ensureLeafletLoaded() {
    if (typeof window.L !== "undefined") {
      console.log("Leaflet already loaded");
      return;
    }

    console.log("Loading Leaflet CSS and JS...");

    // Load CSS first
    await loadCSS("https://unpkg.com/leaflet@1.9.4/dist/leaflet.css");
    console.log("Leaflet CSS loaded");

    // Load JS
    await loadJS("https://unpkg.com/leaflet@1.9.4/dist/leaflet.js");
    console.log("Leaflet JS loaded");

    // Wait for full initialization
    let attempts = 0;
    while (typeof window.L === "undefined" && attempts < 50) {
      await new Promise((resolve) => setTimeout(resolve, 100));
      attempts++;
    }

    if (typeof window.L !== "undefined") {
      console.log("Leaflet fully initialized");
    } else {
      throw new Error("Leaflet failed to initialize");
    }
  }

  async initMap() {
    const container = this.mapRef.el;
    if (!container) {
      console.log("No container found for check-in map");
      return;
    }

    console.log("Initializing check-in map...");

    try {
      await this.ensureLeafletLoaded();

      const lat = parseFloat(this.props.record.data.in_latitude);
      const lng = parseFloat(this.props.record.data.in_longitude);

      console.log(`Check-in coordinates: ${lat}, ${lng}`);

      if (!lat || !lng || isNaN(lat) || isNaN(lng)) {
        container.innerHTML =
          '<div style="display:flex;align-items:center;justify-content:center;height:350px;color:#666;background:#f8f9fa;border-radius:4px;border:1px solid #ddd;">No check-in location data</div>';
        return;
      }

      // Create unique map ID
      const mapId = `checkin-map-${Math.random().toString(36).substr(2, 9)}`;

      // Clear container and set up map div with explicit styling
      container.innerHTML = `
                <div id="${mapId}" style="
                    height: 350px !important; 
                    width: 500px !important; 
                    background: #ddd; 
                    border: 1px solid #ccc;
                    position: relative !important;
                    z-index: 1 !important;
                "></div>
            `;

      // Wait for DOM element to be ready
      await new Promise((resolve) => setTimeout(resolve, 300));

      const mapElement = document.getElementById(mapId);
      if (!mapElement) {
        console.error("Map element not found:", mapId);
        return;
      }

      console.log("Creating check-in map with ID:", mapId);

      // Create map with explicit options
      const map = window.L.map(mapId, {
        preferCanvas: false,
        zoomControl: true,
        attributionControl: true,
        zoomAnimation: false,
        fadeAnimation: false,
        markerZoomAnimation: false,
      }).setView([lat, lng], 19);

      console.log("Map instance created, adding tiles...");

      // Add tile layer
      const tileLayer = window.L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
          attribution: "© OpenStreetMap contributors",
          maxZoom: 19,
          crossOrigin: true,
        }
      );

      tileLayer.addTo(map);

      // Add marker
      const marker = window.L.marker([lat, lng]).addTo(map);
      marker.bindPopup(`
                <div style="min-width: 200px;">
                    <h4 style="margin: 0 0 10px 0; color: #28a745;">Check In Location</h4>
                    <p><strong>Latitude:</strong> ${lat.toFixed(6)}</p>
                    <p><strong>Longitude:</strong> ${lng.toFixed(6)}</p>
                </div>
            `);

      this.map = map;
      console.log("Check-in map created successfully");

      // Multiple resize attempts
      setTimeout(() => {
        if (this.map) {
          this.map.invalidateSize(true);
          console.log("Map size invalidated (first)");
        }
      }, 100);

      setTimeout(() => {
        if (this.map) {
          this.map.invalidateSize(true);
          this.map.setView([lat, lng], 19);
          console.log("Map refreshed and centered");
        }
      }, 500);
    } catch (error) {
      console.error("Error creating check-in map:", error);
      container.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;height:350px;color:#e74c3c;background:#fdf2f2;border-radius:4px;border:1px solid #ddd;">Error loading map: ${error.message}</div>`;
    }
  }

  cleanup() {
    if (this.map) {
      console.log("Cleaning up check-in map");
      this.map.remove();
    }
  }
}

// Check-out widget component
class LeafletMapCheckOut extends Component {
  setup() {
    this.mapRef = useRef("mapContainer");
    onMounted(() => this.initMap());
    onWillUnmount(() => this.cleanup());
  }

  async ensureLeafletLoaded() {
    if (typeof window.L !== "undefined") {
      console.log("Leaflet already loaded");
      return;
    }

    console.log("Loading Leaflet CSS and JS...");

    // Load CSS first
    await loadCSS("https://unpkg.com/leaflet@1.9.4/dist/leaflet.css");
    console.log("Leaflet CSS loaded");

    // Load JS
    await loadJS("https://unpkg.com/leaflet@1.9.4/dist/leaflet.js");
    console.log("Leaflet JS loaded");

    // Wait for full initialization
    let attempts = 0;
    while (typeof window.L === "undefined" && attempts < 50) {
      await new Promise((resolve) => setTimeout(resolve, 100));
      attempts++;
    }

    if (typeof window.L !== "undefined") {
      console.log("Leaflet fully initialized");
    } else {
      throw new Error("Leaflet failed to initialize");
    }
  }

  async initMap() {
    const container = this.mapRef.el;
    if (!container) {
      console.log("No container found for check-out map");
      return;
    }

    console.log("Initializing check-out map...");

    try {
      await this.ensureLeafletLoaded();

      const lat = parseFloat(this.props.record.data.out_latitude);
      const lng = parseFloat(this.props.record.data.out_longitude);

      console.log(`Check-out coordinates: ${lat}, ${lng}`);

      if (!lat || !lng || isNaN(lat) || isNaN(lng)) {
        container.innerHTML =
          '<div style="display:flex;align-items:center;justify-content:center;height:350px;color:#666;background:#f8f9fa;border-radius:4px;border:1px solid #ddd;">No check-out location data</div>';
        return;
      }

      // Create unique map ID
      const mapId = `checkout-map-${Math.random().toString(36).substr(2, 9)}`;

      // Clear container and set up map div with explicit styling
      container.innerHTML = `
                <div id="${mapId}" style="
                    height: 350px !important; 
                    width: 500px !important; 
                    background: #ddd; 
                    border: 1px solid #ccc;
                    position: relative !important;
                    z-index: 1 !important;
                "></div>
            `;

      // Wait for DOM element to be ready
      await new Promise((resolve) => setTimeout(resolve, 300));

      const mapElement = document.getElementById(mapId);
      if (!mapElement) {
        console.error("Map element not found:", mapId);
        return;
      }

      console.log("Creating check-out map with ID:", mapId);

      // Create map with explicit options
      const map = window.L.map(mapId, {
        preferCanvas: false,
        zoomControl: true,
        attributionControl: true,
        zoomAnimation: false,
        fadeAnimation: false,
        markerZoomAnimation: false,
      }).setView([lat, lng], 19);

      console.log("Map instance created, adding tiles...");

      // Add tile layer
      const tileLayer = window.L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
          attribution: "© OpenStreetMap contributors",
          maxZoom: 19,
          crossOrigin: true,
        }
      );

      tileLayer.addTo(map);

      // Add marker
      const marker = window.L.marker([lat, lng]).addTo(map);
      marker.bindPopup(`
                <div style="min-width: 200px;">
                    <h4 style="margin: 0 0 10px 0; color: #dc3545;">Check Out Location</h4>
                    <p><strong>Latitude:</strong> ${lat.toFixed(6)}</p>
                    <p><strong>Longitude:</strong> ${lng.toFixed(6)}</p>
                </div>
            `);

      this.map = map;
      console.log("Check-out map created successfully");

      // Multiple resize attempts
      setTimeout(() => {
        if (this.map) {
          this.map.invalidateSize(true);
          console.log("Map size invalidated (first)");
        }
      }, 100);

      setTimeout(() => {
        if (this.map) {
          this.map.invalidateSize(true);
          this.map.setView([lat, lng], 19);
          console.log("Map refreshed and centered");
        }
      }, 500);
    } catch (error) {
      console.error("Error creating check-out map:", error);
      container.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;height:350px;color:#e74c3c;background:#fdf2f2;border-radius:4px;border:1px solid #ddd;">Error loading map: ${error.message}</div>`;
    }
  }

  cleanup() {
    if (this.map) {
      console.log("Cleaning up check-out map");
      this.map.remove();
    }
  }
}

// Templates
LeafletMapCheckIn.template = "hr_attendance_maps.LeafletMapTemplate";
LeafletMapCheckOut.template = "hr_attendance_maps.LeafletMapTemplate";

console.log("Registering leaflet widgets...");

// Register widgets
registry.category("view_widgets").add("leaflet_map_checkin", {
  component: LeafletMapCheckIn,
});

registry.category("view_widgets").add("leaflet_map_checkout", {
  component: LeafletMapCheckOut,
});

console.log("Leaflet widgets registered successfully");
