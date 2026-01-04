import React from 'react';
import { Clock } from 'lucide-react';

export default function DistanceSlider({ cities, selectedCityIndex, onCityChange }) {

  if (!cities || cities.length === 0) {
    // Show a default city with distance 0 if nothing is loaded
    return (
      <div className="w-full p-6 bg-white rounded-xl shadow-sm border border-gray-100 flex justify-center items-center">
        <div className="text-gray-500">Loading cities...</div>
      </div>
    );
  }

  const isAllSelected = selectedCityIndex === cities.length;
  // Defensive: fallback to first city, or a default object if cities is empty
  const selectedCity = isAllSelected 
    ? { city: 'All Events', distance_miles: 'All' }
    : (cities[selectedCityIndex] || cities[0] || { city: 'Current Location', distance_miles: 0 });

  return (
    <div className="w-full p-6 bg-white rounded-xl shadow-sm border border-gray-100">
      <div className="flex justify-between items-center mb-8">
        <h3 className="text-lg font-semibold text-gray-800">Distance</h3>
        <div className="text-right">
          <span className="text-2xl font-bold text-blue-600">
            {isAllSelected ? 'All' : (typeof selectedCity.distance_miles === 'number' && !isNaN(selectedCity.distance_miles)
              ? selectedCity.distance_miles.toFixed(1)
              : '0.0')}
          </span>
          <span className="text-gray-500 ml-1">{isAllSelected ? 'Events' : 'miles'}</span>
        </div>
      </div>

      <div className="relative mb-12">
        <input
          type="range"
          min="0"
          max={cities.length}
          step="1"
          value={selectedCityIndex}
          onChange={(e) => onCityChange(parseInt(e.target.value))}
          className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
        />
        
        <div className="absolute w-full flex justify-between px-1 mt-4">
          {/* Render ticks for cities */}
          {cities.map((city, index) => (
            <div 
              key={city.city}
              className="flex flex-col items-center"
              style={{ 
                width: `${100 / (cities.length + 1)}%`,
                opacity: index === selectedCityIndex ? 1 : 0.3 
              }}
            >
              <div className={`w-0.5 h-2 mb-2 ${index === selectedCityIndex ? 'bg-blue-600' : 'bg-gray-300'}`} />
              {index === selectedCityIndex && (
                <div className="absolute top-6 transform -translate-x-1/2 whitespace-nowrap flex flex-col items-center bg-white p-2 rounded shadow-lg border border-gray-100 z-10">
                  <span className="font-medium text-gray-900 text-sm">{city.city.split(',')[0]}</span>
                  <div className="flex items-center gap-1 text-xs text-gray-500 mt-0.5">
                    <Clock className="w-3 h-3" />
                    <span>{city.duration_text}</span>
                  </div>
                </div>
              )}
            </div>
          ))}
          
          {/* Render tick for "All" */}
          <div 
            className="flex flex-col items-center"
            style={{ 
              width: `${100 / (cities.length + 1)}%`,
              opacity: isAllSelected ? 1 : 0.3 
            }}
          >
            <div className={`w-0.5 h-2 mb-2 ${isAllSelected ? 'bg-blue-600' : 'bg-gray-300'}`} />
            {isAllSelected && (
              <div className="absolute top-6 transform -translate-x-1/2 whitespace-nowrap flex flex-col items-center bg-white p-2 rounded shadow-lg border border-gray-100 z-10">
                <span className="font-medium text-gray-900 text-sm">All Events</span>
                <div className="flex items-center gap-1 text-xs text-gray-500 mt-0.5">
                  <span>Everywhere</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
      
      <div className="mt-16 text-sm text-gray-500 text-center">
        Slide to expand search radius from Santa Cruz
      </div>
    </div>
  );
}
